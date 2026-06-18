# sends 30 test questions to the local /ask endpoint
# mix of questions that should be answerable and a few that won't be
# run this after /ingest to get some data in the analytics dashboard

import requests
import time

BASE = "http://localhost:8000"

questions = [
    "What are AWS responsibilities?",
    "What is AWS data privacy policy?",
    "Can AWS access my content?",
    "What are my responsibilities as an AWS customer?",
    "How does AWS handle security?",
    "What happens if I don't pay my AWS bill?",
    "Can AWS suspend my account?",
    "What is the termination policy?",
    "How much notice does AWS give before discontinuing a service?",
    "What are the payment terms?",
    "How are taxes handled in the AWS agreement?",
    "What is the dispute resolution process?",
    "What is AWS's liability limit?",
    "Can I transfer my AWS account?",
    "What are the acceptable use policies?",
    "What is the governing law for the AWS agreement?",
    "How does AWS define 'Your Content'?",
    "What is an End User under the AWS agreement?",
    "Does AWS provide service level agreements?",
    "What happens to my data if I terminate my account?",
    "Can AWS change fees without notice?",
    "What is the AWS intellectual property policy?",
    "How does AWS handle government data requests?",
    "What is the indemnification clause?",
    "Can AWS be held liable for indirect damages?",
    "What is the third-party content policy?",
    "Does AWS offer refunds?",
    "What counts as a Facility in the AWS agreement?",
    "What is the best pizza recipe?",          # out-of-scope
    "Who won the FIFA World Cup in 2022?",     # out-of-scope
]

print(f"Sending {len(questions)} queries to {BASE}/ask...\n")

for i, q in enumerate(questions, 1):
    try:
        r = requests.post(f"{BASE}/ask", json={"question": q}, timeout=120)
        if r.status_code == 200:
            data = r.json()
            tag = "✅" if data["answer_found"] else "❌"
            print(f"[{i:02d}] {tag} ({data['response_time_seconds']}s) {q[:65]}")
        else:
            print(f"[{i:02d}] HTTP {r.status_code}: {q[:65]}")
    except Exception as e:
        print(f"[{i:02d}] error: {e}")
    time.sleep(0.5)

print("\nDone. Visit /analytics to see the results.")
