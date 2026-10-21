"""Run the evaluation questions through the bot and write two reports:
eval/results-<model>.md (a table to read) and eval/review-<model>.csv (opens in Excel, with a column to mark by hand).

Run: python -m eval.run_eval                  (answers with CHAT_MODEL from config.py)
     python -m eval.run_eval gpt-4.1-mini     (answers with another model, to compare)
"""
import csv
import json
import sys
import time
from datetime import date
from pathlib import Path

import config
from rag.answer import answer

QUESTIONS_PATH = Path("eval/questions.json")


def check(item: dict, result: dict) -> bool:
    """True if the bot did what we expected: the right kind of refusal, or an answer from the expected page."""
    if "קטע" in result["answer"]:
        return False                                       # internal word: the user never sees the chunks
    if item["expect"] == "closing":
        return result.get("reason") == "closing"
    if item["expect"] == "refuse":
        if result["answerable"]:
            return False
        if "reason" in item and result.get("reason") != item["reason"]:
            return False                                   # e.g. expected a clarifying question, got "not on the site"
        if "offer" in item and ("רוצה שאסביר" in result["answer"]) != item["offer"]:
            return False                                   # expected the "want me to explain?" offer, or expected none
        return True
    return result["answerable"] and any(item["url"] in source["url"] for source in result["sources"])


def cell(text: str) -> str:
    """Make text safe for one cell of a Markdown table."""
    return text.replace("|", "\\|").replace("\n", "<br>")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")   # print Hebrew correctly in the Windows terminal
    if len(sys.argv) > 1:
        config.CHAT_MODEL = sys.argv[1]

    items = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    history, rows, review, times = [], [], [], []
    passed = {"answer": 0, "refuse": 0}
    totals = {"answer": 0, "refuse": 0}

    for item in items:
        if not item.get("follow_up"):
            history = []                       # a new conversation, unless this is a follow-up question
        start = time.time()
        result = answer(item["question"], history)
        seconds = time.time() - start
        ok = check(item, result)

        times.append(seconds)
        group = "answer" if item["expect"] == "answer" else "refuse"   # a closing reply counts with the refusals
        totals[group] += 1
        passed[group] += ok
        history += [{"role": "user", "content": item["question"]},
                    {"role": "assistant", "content": result["answer"]}]

        did = "ענה" if result["answerable"] else f"סירב ({result.get('reason')})"
        expected = {"answer": "לענות", "refuse": "לסרב", "closing": "לסיים בנימוס"}[item["expect"]]
        sources = [source["url"] for source in result["sources"]]
        rows.append(f"| {item['id']} | {'✅' if ok else '❌'} | {cell(item['question'])} | {expected} "
                    f"| {did} | {seconds:.1f} | {cell(result['answer'])} | {'<br>'.join(sources)} |")
        review.append([item["id"], item["type"], item["question"], expected, did, result["answer"],
                       "\n".join(sources), "עבר" if ok else "נכשל", "", ""])
        print(f"{'✅' if ok else '❌'} {item['id']:>2}  {seconds:4.1f}s  {item['question']}")

    summary = (f"model: {config.CHAT_MODEL} | date: {date.today()} | "
               f"answers: {passed['answer']}/{totals['answer']} | refusals: {passed['refuse']}/{totals['refuse']} | "
               f"average time: {sum(times) / len(times):.1f}s")
    table = ["| # | עבר | שאלה | צפוי | מה הבוט עשה | שניות | תשובה | מקורות |",
             "|---|---|---|---|---|---|---|---|", *rows]
    results_path = Path(f"eval/results-{config.CHAT_MODEL}.md")
    results_path.write_text(f"# Evaluation results\n\n{summary}\n\n" + "\n".join(table) + "\n", encoding="utf-8")

    review_path = Path(f"eval/review-{config.CHAT_MODEL}.csv")
    with review_path.open("w", encoding="utf-8-sig", newline="") as f:   # utf-8-sig: Excel shows Hebrew correctly
        writer = csv.writer(f)
        writer.writerow(["#", "סוג שאלה", "שאלה", "צפוי", "מה הבוט עשה", "תשובה", "מקורות",
                         "בדיקה אוטומטית", "הסימון שלי (עבר / נכשל)", "הערות"])
        writer.writerows(review)

    print(summary)
    print(f"reports: {results_path}  |  {review_path}")


if __name__ == "__main__":
    main()
