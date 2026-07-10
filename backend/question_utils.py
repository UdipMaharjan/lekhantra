import re


def clean_text(text: str) -> str:
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_important_sentences(text: str, limit: int = 8) -> list[str]:
    text = clean_text(text)

    sentences = re.split(r"(?<=[.!?]) +", text)

    important_sentences = []

    for sentence in sentences:
        sentence = sentence.strip()

        if len(sentence.split()) >= 6:
            important_sentences.append(sentence)

        if len(important_sentences) == limit:
            break

    return important_sentences


def generate_viva_questions(text: str) -> list[dict]:
    important_sentences = get_important_sentences(text, limit=8)

    questions = []

    for index, sentence in enumerate(important_sentences, start=1):
        questions.append({
            "question_no": index,
            "question": f"Explain this in your own words: {sentence}",
            "answer_hint": sentence
        })

    return questions


def generate_exam_questions(text: str) -> list[dict]:
    important_sentences = get_important_sentences(text, limit=8)

    questions = []

    for index, sentence in enumerate(important_sentences, start=1):
        questions.append({
            "question_no": index,
            "question": f"Write a short note on: {sentence[:80]}...",
            "marks": 5,
            "answer_hint": sentence
        })

    return questions