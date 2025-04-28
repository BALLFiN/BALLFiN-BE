import re
from typing import Any, Dict, List, Tuple
from app.db.neo4j import neo4j_driver,client,cached_entities

# 입력 텍스트에서 FinDKG의 entity를 식별하는 함수
def identify_entities_in_text(text: str, entities: set[str]) -> set[str]:
    """
    긴 엔티티 우선 매칭 + 마스킹 방식
    - entities를 길이 내림차순 정렬
    - 하나씩 찾아나가면서, 이미 검출된(마스크된) 구간은 스킵
    """
    identified = set()
    text_len = len(text)
    # 텍스트 길이만큼 False로 초기화(아직 매칭된 곳 없음)
    covered = [False] * text_len

    # 길이 내림차순으로 정렬해야 'SK하이닉스'가 'SK'보다 먼저 매칭됨
    for ent in sorted(entities, key=len, reverse=True):
        start = 0
        while True:
            idx = text.find(ent, start)
            if idx == -1:
                break
            # 이 구간(ent 길이만큼)이 모두 아직 커버되지 않았다면 매칭 처리
            if not any(covered[idx : idx + len(ent)]):
                identified.add(ent)
                # 매칭된 구간을 True로 마스크
                for i in range(idx, idx + len(ent)):
                    covered[i] = True
            start = idx + 1

    return identified

def ask_llm(prompt: str) -> str:
    """LLM에 질문하고 응답 받기"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "너는 경제 분석 전문가이자, 뉴스 분석을 위한 지식 선별 전문가이다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"LLM API 호출 오류: {e}")
        # 기본 응답 반환
        return "필요한 관계: []\n확장할 엔티티: 없음"

def get_one_hop_structure(entities:list[str]) -> List[Dict[str, Any]]:
    """
    주어진 엔티티에서 1-hop 이웃을 가져오는 함수
    단방향(->)으로만 탐색
    """
    query = """
    MATCH (start)
    WHERE start.name IN $entities
    MATCH (start)-[r]->(neighbor)
    RETURN start.name AS source,
           type(r) AS relation,
           properties(r) AS relation_property,
           neighbor.name AS target
    """
    try:
        with neo4j_driver.session() as session:
            results = session.run(query, entities=entities)
            return [record.data() for record in results]
    except Exception as e:
        print(f"Neo4j 쿼리 오류: {e}")
        return []

def parse_llm_response(response: str,graph_snapshot:list) -> Tuple[List[int], List[str]]:
    """LLM 응답을 파싱하여 필요한 관계와 확장할 엔티티 추출"""
    try:
        # 정규식을 사용하여 필요한 관계 추출
        relevant_indices = []
        relation_match = re.search(r'필요한 관계:?\s*\[(.*?)\]', response, re.IGNORECASE)
        if relation_match:
            indices_str = relation_match.group(1).strip()
            if indices_str:
                # 쉼표로 구분된 숫자 추출
                relevant_indices = [int(idx.strip()) for idx in indices_str.split(',') if idx.strip().isdigit()]
        
        # 확장할 엔티티 추출
        expand_entities = [graph_snapshot[i]['target'] for i in relevant_indices]
        
        return relevant_indices, expand_entities
    except Exception as e:
        print(f"응답 파싱 오류: {e}")
        return [], []

def evaluate_graph_relevance(graph_snapshot, news_text):
    """
    LLM을 사용하여 그래프의 관련성을 평가하고 확장할 엔티티 결정
    """
    if not graph_snapshot:
        return [], []
    
    edge_list_str = "\n".join([
        f"{i}. {e['source']} -[{e['relation']}]- {e['target']}" 
        for i, e in enumerate(graph_snapshot)
    ])
    
    prompt = f"""
    다음은 분석할 뉴스와 그것과 관련된 지식그래프 정보입니다:

    뉴스:
    {edge_list_str}
    
    뉴스:
    "{news_text}"
    
    
    위 지식그래프 중 뉴스 분석에 필요한 트리플(Triple)의 번호를 선택하세요. 
    (예: [0, 2, 5], 없다면 빈 리스트 []를 반환하세요.)
    
    반드시 답변 형식을 지켜주세요.
    
    답변 형식:
    필요한 관계: [0, 1, 3]
    """
    
    response = ask_llm(prompt)
    relevant_indices, expand_entities = parse_llm_response(response,graph_snapshot)
    
    # 유효한 인덱스만 필터링 / 범위 초과할 수 있으므로 체크
    valid_indices = [idx for idx in relevant_indices if 0 <= idx < len(graph_snapshot)]
    relevant_edges = [graph_snapshot[i] for i in valid_indices]
    
    return relevant_edges, expand_entities

def intelligent_graph_expansion(start_entities, news_text, max_hops=3):
    """
    LLM 기반 지능형 그래프 확장 (여러 시작 엔티티 지원)
    """
    if not start_entities:
        print("시작 엔티티가 없습니다.")
        return []
    
    # start_entities가 set이면 그대로 사용, 아니면 set으로 변환
    if isinstance(start_entities, set):
        entities_set = start_entities
    else:
        entities_set = set([start_entities]) if isinstance(start_entities, str) else set(start_entities)
    
    visited_nodes = set()
    to_expand = list(entities_set)
    all_relevant_graph = []
    
    print(f"뉴스에서 검출된 시작 엔티티: {', '.join(entities_set)}")
    
    for hop in range(max_hops):
        if not to_expand:
            print("더 이상 확장할 엔티티가 없습니다.")
            break
            
        print(f"\n[Hop {hop+1}] 확장 중인 엔티티: {', '.join(to_expand)}")
        
        # 현재 확장할 엔티티에서 1-hop 이웃 가져오기
        graph_snapshot = get_one_hop_structure(to_expand)
        # 방문처리
        visited_nodes.update(to_expand)

        if not graph_snapshot:
            print(f"더 이상 확장할 노드가 없습니다.")
            break
            
        # LLM에게 관련성 평가 요청
        relevant_edges, next_entities = evaluate_graph_relevance(graph_snapshot, news_text)
        
        
        # 관련 엣지 저장
        all_relevant_graph.extend(relevant_edges)
        
        # 다음 확장할 엔티티 설정 (이미 방문한 노드 제외)
        to_expand = [entity for entity in next_entities if entity not in visited_nodes]
        
        print(f"선택된 관련 엣지: {len(relevant_edges)}개 / 발견된 엣지: {len(graph_snapshot)}개")
        print(f"다음 확장할 엔티티: {to_expand}")
    
    return all_relevant_graph

def create_graph_structure(query:str) -> str:
    '''
    뉴스 텍스트와 검출할 엔티티 set을 받아 분석에 필요한 지식그래프를 텍스트 형태로 생성
    '''
    
    entities_set = identify_entities_in_text(query, cached_entities)
    if not entities_set:
        return "분석할 기업 엔티티가 없습니다."
    print("🕸️지식그래프 생성 도구 사용, 검출 기업 : ",entities_set)
    
    # entities_set을 시작으로 그래프 확장
    relevant_graph = intelligent_graph_expansion(entities_set, query)

    if not relevant_graph:
        return "관련 그래프 정보를 찾을 수 없습니다."
    
    # 그래프 정보를 구조화된 텍스트로 변환
    graph_text = "\n".join([
    f"- ({e['source']}) -[{e['relation']}"+ 

    (f",{e['relation_property']}" if e['relation_property'] and e['relation_property'] != {} else "")+

    f"]-> ({e['target']})" 
    for e in relevant_graph
    ])

    return graph_text

def analyze_news_with_graph( news_text: str, cached_enteities: set[str]) -> str:
    """
    엔티티 집합과 뉴스 텍스트를 받아 그래프 기반 뉴스 분석 수행
    """

    graph_text :str = create_graph_structure(news_text, cached_entities)
    
    
    # LLM에게 최종 분석 요청
    prompt = f"""
     다음은 뉴스와 관련된 기업 관계 정보입니다:
    
     {graph_text}
    
     뉴스:
     "{news_text}"
    
    위 정보를 배경지식으로 활용할 수 있다면 활용하면서, 뉴스가 관련 기업들에 미치는 영향과 의미를 심층적으로 분석해주세요.
    """
    print(f'\n 최종 지식 그래프{graph_text}\n')
    analysis = ask_llm(prompt)
    return analysis

