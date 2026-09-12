import time

from fastapi import APIRouter, HTTPException

from ..config import get_settings
from ..dataset import QUESTIONS
from ..db import create_experiment, get_experiment, list_experiments, save_output
from ..llm import LLMError, complete, objective_match
from ..schemas import RunRequest

router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.get("")
def experiments():
    return list_experiments()


@router.get("/{experiment_id}")
def experiment(experiment_id: int):
    result = get_experiment(experiment_id)
    if not result:
        raise HTTPException(404, "Experiment not found")
    return result


async def run_one(question: dict, request: RunRequest, model: str) -> dict:
    started = time.perf_counter()
    calls = 0
    tokens = 0

    async def ask(prompt: str, role: str = "solver"):
        nonlocal calls, tokens
        result = await complete(prompt, question["question"], question["reference_answer"], role, model)
        calls += 1
        tokens += result.tokens
        return result.text

    solver = await ask(
        f"Solve this question. Return the answer and one or two concise supporting facts:\n"
        f"{question['question']}"
    )
    agents = {"solver": solver}
    final = solver
    if request.mode == "debate":
        rounds = []
        for round_no in range(1, request.rounds + 1):
            answer_before_critique = final
            critic = await ask(
                f"Critique this proposed answer for correctness, missing evidence, and logical "
                f"errors. Be concise.\nQuestion: {question['question']}\nAnswer: {final}",
                "critic",
            )
            revision = await ask(
                f"Revise the answer using the critique. Return only a concise answer with brief "
                f"evidence.\nQuestion: {question['question']}\nOriginal: {final}\nCritique: {critic}",
                "revision",
            )
            rounds.append({
                "round": round_no,
                "answer_before_critique": answer_before_critique,
                "critic": critic,
                "revised_answer": revision,
            })
            final = revision
        judge = await ask(
            f"Evaluate the revised answer against the question. State whether it is correct and "
            f"why in one sentence.\nQuestion: {question['question']}\nAnswer: {final}",
            "judge",
        )
        agents.update({"rounds": rounds, "judge": judge})

    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    return {
        "question": question["question"],
        "category": question["category"],
        "reference_answer": question["reference_answer"],
        "final_answer": final,
        "correct": objective_match(final, question["reference_answer"]) if question["reference_answer"] else None,
        "evaluated": bool(question["reference_answer"]),
        "status": "ok",
        "agents": agents,
        "execution_time_ms": elapsed_ms,
        "llm_calls": calls,
        "token_usage": tokens,
    }


async def execute(request: RunRequest):
    settings = get_settings()
    model = request.model or settings.openai_model
    if request.question:
        selected = [{"id": 0, "question": request.question, "reference_answer": "", "category": "custom"}]
    else:
        ids = set(request.question_ids or [q["id"] for q in QUESTIONS])
        selected = [q for q in QUESTIONS if q["id"] in ids]
    if not selected:
        raise HTTPException(400, "No valid question IDs supplied")
    exp_id = create_experiment(request.name, request.mode, request.rounds, model)
    for question in selected:
        try:
            output = await run_one(question, request, model)
        except LLMError as exc:
            output = {
                "question": question["question"],
                "category": question["category"],
                "reference_answer": question["reference_answer"],
                "final_answer": "Provider error: no answer produced.",
                "correct": None,
                "evaluated": False,
                "status": "error",
                "agents": {"error": str(exc)},
                "execution_time_ms": 0,
                "llm_calls": 0,
                "token_usage": 0,
            }
        save_output(exp_id, question["id"], output)
    result = get_experiment(exp_id)
    evaluated = [item for item in result["outputs"] if item.get("evaluated")]
    correct = sum(item["correct"] is True for item in evaluated)
    result["summary"] = (
        f"{correct}/{len(evaluated)} correct ({correct / len(evaluated) * 100:.1f}%)"
        if evaluated else "Not objectively evaluated"
    )
    result["metrics"] = metrics(result["outputs"])
    return result


def metrics(outputs: list[dict]) -> dict:
    count = max(1, len(outputs))
    return {
        "accuracy": round(sum(item["correct"] is True for item in outputs if item.get("evaluated")) / max(1, sum(item.get("evaluated", False) for item in outputs)) * 100, 2),
        "avg_time_ms": round(sum(item["execution_time_ms"] for item in outputs) / count, 2),
        "avg_llm_calls": round(sum(item["llm_calls"] for item in outputs) / count, 2),
        "avg_tokens": round(sum(item["token_usage"] for item in outputs) / count, 2),
    }


@router.post("/run")
async def run_experiment(request: RunRequest):
    return await execute(request)


@router.post("/compare")
async def compare_experiments(request: RunRequest):
    """Run both methods on the same questions and return a research-ready comparison."""
    single = request.model_copy(update={"mode": "single", "name": f"{request.name} — single"})
    debate = request.model_copy(update={"mode": "debate", "name": f"{request.name} — debate"})
    single_result = await execute(single)
    debate_result = await execute(debate)
    a, b = single_result["metrics"], debate_result["metrics"]
    return {
        "single": single_result,
        "debate": debate_result,
        "comparison": {
            "accuracy_change_percentage_points": round(b["accuracy"] - a["accuracy"], 2),
            "time_change_percentage": round((b["avg_time_ms"] - a["avg_time_ms"]) / max(a["avg_time_ms"], 1) * 100, 2),
            "call_change_percentage": round((b["avg_llm_calls"] - a["avg_llm_calls"]) / max(a["avg_llm_calls"], 1) * 100, 2),
            "token_change_percentage": round((b["avg_tokens"] - a["avg_tokens"]) / max(a["avg_tokens"], 1) * 100, 2),
        },
    }
