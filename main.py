from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Union
import json
import os
from pathlib import Path

app = FastAPI()

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)


class Question(BaseModel):
    id: Optional[int] = None
    type: str  # "single", "multiple", "judge", "fill", "cloze"
    content: str
    options: Optional[Union[List[str], List[List[str]]]] = None
    answer: Any
    explanation: Optional[str] = None


class AddQuestionRequest(BaseModel):
    library: str
    question: Question


class UpdateQuestionRequest(BaseModel):
    library: str
    question_id: int
    question: Question


class DeleteQuestionRequest(BaseModel):
    library: str
    question_id: int


def scan_libraries() -> List[str]:
    libraries = []
    if DATA_DIR.exists():
        for file in DATA_DIR.glob("*.json"):
            libraries.append(file.stem)
    return sorted(libraries)


def load_library(name: str) -> List[Dict[str, Any]]:
    file_path = DATA_DIR / f"{name}.json"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Library not found")
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read().strip()
        if not content:
            return []
        return json.loads(content)


def save_library(name: str, questions: List[Dict[str, Any]]):
    file_path = DATA_DIR / f"{name}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)


@app.get("/api/libraries")
def get_libraries():
    return {"libraries": scan_libraries()}


@app.get("/api/library/{name}")
def get_library(name: str):
    return {"name": name, "questions": load_library(name)}


@app.post("/api/add-question")
def add_question(request: AddQuestionRequest):
    try:
        questions = load_library(request.library)
    except HTTPException:
        questions = []

    new_question = request.question.dict()
    # 总是忽略用户提供的 id，由后端统一生成
    if questions:
        max_id = max(q.get("id", 0) for q in questions)
        new_question["id"] = max_id + 1
    else:
        new_question["id"] = 1

    questions.append(new_question)
    save_library(request.library, questions)
    return {"success": True, "question": new_question}


@app.post("/api/batch-import")
def batch_import(library: str, questions: List[Question]):
    try:
        existing = load_library(library)
    except HTTPException:
        existing = []

    max_id = max((q.get("id", 0) for q in existing), default=0)
    added = []

    for q in questions:
        q_dict = q.dict()
        max_id += 1
        q_dict["id"] = max_id
        existing.append(q_dict)
        added.append(q_dict)

    save_library(library, existing)
    return {"success": True, "added": len(added)}


@app.put("/api/update-question")
def update_question(request: UpdateQuestionRequest):
    questions = load_library(request.library)
    idx = next((i for i, q in enumerate(questions) if q.get("id") == request.question_id), None)
    if idx is None:
        raise HTTPException(status_code=404, detail="Question not found")
    updated_q = request.question.dict()
    updated_q["id"] = request.question_id  # 保持原有 id
    questions[idx] = updated_q
    save_library(request.library, questions)
    return {"success": True, "question": updated_q}


@app.delete("/api/delete-question")
def delete_question(request: DeleteQuestionRequest):
    questions = load_library(request.library)
    idx = next((i for i, q in enumerate(questions) if q.get("id") == request.question_id), None)
    if idx is None:
        raise HTTPException(status_code=404, detail="Question not found")
    deleted = questions.pop(idx)
    save_library(request.library, questions)
    return {"success": True, "deleted_id": deleted.get("id")}


app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
    
