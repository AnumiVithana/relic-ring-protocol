"""
run.py
------
Entry point. Run with: python run.py
Then open http://localhost:8000 in a browser.
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.api:app", host="0.0.0.0", port=8000, reload=True)
