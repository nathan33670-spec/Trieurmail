import time

from fastapi.testclient import TestClient

from trieurmail.web.app import create_app


def wait(client, job):
    for _ in range(200):
        job = client.get(f"/api/jobs/{job['id']}").json()
        if job["status"] != "running":
            assert job["status"] == "done", job["error"]
            return job["result"]
        time.sleep(0.05)
    raise AssertionError("tâche trop longue")


def test_api_end_to_end(ctx):
    with TestClient(create_app(ctx)) as client:
        assert client.get("/").status_code == 200
        state = client.get("/api/state").json()
        assert state["configured"] == {"llm": True, "mail": True}
        assert client.get("/api/timeline").json()["total"] > 0
        assert client.put("/api/scope", json={"folders": ["INBOX"], "since": None, "until": None}).status_code == 200
        wait(client, client.post("/api/sync").json())
        items = client.get("/api/messages?limit=5").json()["items"]
        key = items[0]["key"]
        msg = client.get("/api/message", params={"key": key}).json()
        assert "Content-Security-Policy" in msg["html_doc"]
        assert client.post("/api/summary", json={"key": key}).json()["summary"]
        assert client.post("/api/message/seen", json={"keys": [key], "seen": False}).status_code == 200
        briefs = wait(client, client.post("/api/briefs", json={"keys": [key]}).json())
        assert briefs
        assert "markdown" in wait(client, client.post("/api/digest", json={"unread_only": True}).json())
        prio = wait(client, client.post("/api/priority").json())
        assert prio["items"]
        rc = client.get("/api/reply-context", params={"key": key}).json()
        with client.stream("POST", "/api/draft", json={"key": key, "tone": "bref"}) as resp:
            text = "".join(resp.iter_text())
        assert '"done": true' in text
        saved = client.post("/api/draft/save", json={"key": key, "to": rc["to"], "subject": rc["subject"], "body": "Merci !"})
        assert saved.json()["status"] == "draft"
        plan = wait(client, client.post("/api/sort/propose", json={"hint": ""}).json())
        plan = client.put(f"/api/sort/plan/{plan['id']}/tree", json={"folders": plan["folders"]}).json()
        plan = wait(client, client.post(f"/api/sort/plan/{plan['id']}/assign").json())
        gid = plan["groups"][0]["id"]
        plan = client.put(f"/api/sort/plan/{plan['id']}/assignments", json={"assignments": {gid: ""}}).json()
        assert plan["assignments"][gid] == ""
        done = wait(client, client.post(f"/api/sort/plan/{plan['id']}/apply").json())
        assert done["status"] == "applied"
        # les secrets ne sont jamais renvoyés
        client.put("/api/settings", json={"llm": {"api_key": "sk-secret"}})
        assert client.get("/api/state").json()["settings"]["llm"]["api_key"] == "••••••••"
        client.put("/api/settings", json={"llm": {"api_key": "••••••••"}})
        assert ctx.settings.llm.api_key == "sk-secret"
