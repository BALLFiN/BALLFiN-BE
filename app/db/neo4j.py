import os
from dotenv import load_dotenv
from neo4j import GraphDatabase
from openai import OpenAI

load_dotenv(override=True)

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
NEO4J_URI      = os.environ["NEO4J_URI"]
NEO4J_USER     = os.environ["NEO4J_USERNAME"]
NEO4J_PW       = os.environ["NEO4J_PASSWORD"]

#드라이버 생성

neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PW))
client = OpenAI(api_key=OPENAI_API_KEY)
try:
    with neo4j_driver.session() as sess:
        ok = sess.run("RETURN 1 AS ok").single()["ok"]
    print(f"✅ Neo4j 연결 성공 (RETURN 1 → {ok})")
except Exception as e:
    print(f"❌ Neo4j 연결 실패: {e}")

try:
    rsp = client.models.list()      # 모델 목록만 받아오기 (가벼움)
    print(f"✅ OpenAI 연결 성공, 보유 모델 {len(rsp.data)}개")
except Exception as e:
    print(f"❌ OpenAI 연결 실패: {e}")

# Neo4j에서 entity 목록을 한번만 가져와 메모리에 캐싱하는 함수
def load_all_entities_from_neo4j():
    entities_set = set()
    with neo4j_driver.session() as session:
        query = "MATCH (e:COMP) RETURN DISTINCT e.name as name"
        results = session.run(query)
        for record in results:
            entities_set.add(record["name"])
    return entities_set

# neo4j의 엔티티 캐싱
cached_entities = load_all_entities_from_neo4j()