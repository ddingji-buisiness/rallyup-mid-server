from fastapi import FastAPI
app = FastAPI()

@app.get("/")
def a():
    return "Hello world"
