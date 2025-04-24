# app.py
import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import subprocess
import requests
import json
import time
import os

class VectorDBApp:
    def __init__(self, root):
        self.root = root
        self.root.title("뉴스 벡터 데이터베이스 관리")
        self.root.geometry("800x600")
        
        self.server_process = None
        self.server_url = "http://localhost:9999"
        
        self.setup_ui()
    
    def setup_ui(self):
        # 프레임 설정
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 서버 제어 프레임
        server_frame = ttk.LabelFrame(main_frame, text="서버 제어", padding="5")
        server_frame.pack(fill=tk.X, pady=5)
        
        self.server_status = ttk.Label(server_frame, text="서버 상태: 중지됨", foreground="red")
        self.server_status.pack(side=tk.LEFT, padx=5)
        
        self.start_btn = ttk.Button(server_frame, text="서버 시작", command=self.start_server)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ttk.Button(server_frame, text="서버 중지", command=self.stop_server, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        # 크롤링 프레임
        crawl_frame = ttk.LabelFrame(main_frame, text="뉴스 크롤링", padding="5")
        crawl_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(crawl_frame, text="키워드:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.keyword_var = tk.StringVar(value="삼성전자")
        ttk.Entry(crawl_frame, textvariable=self.keyword_var, width=30).grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        
        ttk.Label(crawl_frame, text="최대 기사 수:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.max_articles_var = tk.StringVar(value="50")
        ttk.Entry(crawl_frame, textvariable=self.max_articles_var, width=10).grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        
        self.crawl_btn = ttk.Button(crawl_frame, text="뉴스 크롤링 및 DB 업데이트", command=self.crawl_news)
        self.crawl_btn.grid(row=2, column=0, columnspan=2, padx=5, pady=5)
        
        # 검색 프레임
        search_frame = ttk.LabelFrame(main_frame, text="벡터 DB 검색", padding="5")
        search_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(search_frame, text="검색어:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.search_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.search_var, width=30).grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        
        ttk.Label(search_frame, text="결과 개수:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.result_count_var = tk.StringVar(value="3")
        ttk.Entry(search_frame, textvariable=self.result_count_var, width=10).grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        
        self.search_btn = ttk.Button(search_frame, text="검색", command=self.search_db)
        self.search_btn.grid(row=2, column=0, columnspan=2, padx=5, pady=5)
        
        # 결과 표시 영역
        result_frame = ttk.LabelFrame(main_frame, text="결과", padding="5")
        result_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.result_text = scrolledtext.ScrolledText(result_frame, width=80, height=20)
        self.result_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
    def start_server(self):
        if not self.server_process or self.server_process.poll() is not None:
            try:
                # server.py 실행
                self.server_process = subprocess.Popen(["python", "app/db/server.py"])
                self.server_status.config(text="서버 상태: 시작 중...", foreground="orange")
                self.start_btn.config(state=tk.DISABLED)
                self.stop_btn.config(state=tk.NORMAL)
                
                # 서버가 시작될 때까지 기다림
                self.root.after(20000, self.check_server_status)
            except Exception as e:
                self.result_text.insert(tk.END, f"서버 시작 오류: {str(e)}\n")
                self.result_text.see(tk.END)
    
    def check_server_status(self):
        try:
            response = requests.get(f"{self.server_url}")
            if response.status_code == 200:
                self.server_status.config(text="서버 상태: 실행 중", foreground="green")
            else:
                self.server_status.config(text=f"서버 상태: 응답 코드 {response.status_code}", foreground="orange")
                self.start_btn.config(state=tk.NORMAL)
        except:
            self.server_status.config(text="서버 상태: 연결 실패", foreground="red")
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
    
    def stop_server(self):
        if self.server_process:
            self.server_process.terminate()
            self.server_status.config(text="서버 상태: 중지됨", foreground="red")
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
    
    def crawl_news(self):
        if not self.is_server_running():
            self.result_text.insert(tk.END, "서버가 실행 중이 아닙니다. 먼저 서버를 시작해주세요.\n")
            self.result_text.see(tk.END)
            return
        
        keyword = self.keyword_var.get()
        try:
            max_articles = int(self.max_articles_var.get())
        except ValueError:
            self.result_text.insert(tk.END, "최대 기사 수는 숫자여야 합니다.\n")
            self.result_text.see(tk.END)
            return
        
        self.result_text.insert(tk.END, f"'{keyword}' 키워드로 최대 {max_articles}개의 뉴스 크롤링 중...\n")
        self.result_text.see(tk.END)
        
        # 백그라운드 스레드에서 크롤링 실행
        threading.Thread(target=self._do_crawl, args=(keyword, max_articles), daemon=True).start()
    
    def _do_crawl(self, keyword, max_articles):
        try:
            response = requests.post(
                f"{self.server_url}/update_news", 
                json={"keyword": keyword, "max_articles": max_articles},
                timeout=300  # 5분 타임아웃
            )
            
            if response.status_code == 200:
                result = response.json()
                self.root.after(0, lambda: self.result_text.insert(tk.END, f"결과: {result['message']}\n"))
            else:
                self.root.after(0, lambda: self.result_text.insert(tk.END, f"에러: 상태 코드 {response.status_code}\n"))
        except Exception as e:
            self.root.after(0, lambda: self.result_text.insert(tk.END, f"크롤링 중 오류 발생: {str(e)}\n"))
        
        self.root.after(0, lambda: self.result_text.see(tk.END))
    
    def search_db(self):
        if not self.is_server_running():
            self.result_text.insert(tk.END, "서버가 실행 중이 아닙니다. 먼저 서버를 시작해주세요.\n")
            self.result_text.see(tk.END)
            return
        
        query = self.search_var.get()
        if not query:
            self.result_text.insert(tk.END, "검색어를 입력해주세요.\n")
            self.result_text.see(tk.END)
            return
        
        try:
            k = int(self.result_count_var.get())
        except ValueError:
            self.result_text.insert(tk.END, "결과 개수는 숫자여야 합니다.\n")
            self.result_text.see(tk.END)
            return
        
        self.result_text.insert(tk.END, f"'{query}' 검색 중...\n")
        self.result_text.see(tk.END)
        
        # 백그라운드 스레드에서 검색 실행
        threading.Thread(target=self._do_search, args=(query, k), daemon=True).start()
    
    def _do_search(self, query, k):
        try:
            response = requests.get(
                f"{self.server_url}/get_documents", 
                params={"query": query, "k": k}
            )
            
            if response.status_code == 200:
                result = response.json()
                
                self.root.after(0, lambda: self.display_search_results(result))
            else:
                self.root.after(0, lambda: self.result_text.insert(tk.END, f"에러: 상태 코드 {response.status_code}\n"))
        except Exception as e:
            self.root.after(0, lambda: self.result_text.insert(tk.END, f"검색 중 오류 발생: {str(e)}\n"))
        
        self.root.after(0, lambda: self.result_text.see(tk.END))
    
    def display_search_results(self, result):
        self.result_text.insert(tk.END, f"검색어 '{result['query']}'에 대한 결과 {len(result['documents'])}개:\n\n")
        
        for i, doc in enumerate(result['documents'], 1):
            self.result_text.insert(tk.END, f"===== 결과 {i} =====\n")
            self.result_text.insert(tk.END, f"{doc['content']}\n")
            self.result_text.insert(tk.END, f"링크: {doc['metadata']['link']}\n\n")
        
        self.result_text.see(tk.END)
    
    def is_server_running(self):
        try:
            response = requests.get(f"{self.server_url}")
            return response.status_code == 200
        except:
            return False

if __name__ == "__main__":
    root = tk.Tk()
    app = VectorDBApp(root)
    root.mainloop()