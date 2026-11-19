"""Paraphrase customer messages with a different local model, keeping the gold order valid.

A paraphrase is kept only if it still contains every anchor of the original
(location, quantity words, and menu words: item names, option names, family
words) and adds no menu word that was not there. Otherwise the template text is
kept. The model is deliberately not the one under test (gpt-oss), so the
assistant is not scored on its own phrasing.
"""

from __future__ import annotations

import json
import re
import urllib.request

PROMPT = (
    "Rewrite this message a student typed into a campus food-ordering kiosk so it sounds like a "
    "different real student: casual, maybe shorter or chattier, contractions or filler words are fine. "
    "Keep every food item, quantity, option and place name with the same words. Do not add or drop "
    "anything, do not answer it. Reply with only the rewritten message.\n\nMessage: {text}"
)
NUMBER_WORDS = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]


def _words(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def _stem(word):
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("es") and re.search(r"(ch|sh|x)es$", word):
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word


def menu_vocabulary(payload, hints, locations):
    vocab = set()
    for item in payload["items"]:
        vocab |= {_stem(w) for w in _words(item["name"])}
        for group in item["option_groups"]:
            for option in group["options"]:
                vocab |= {_stem(w) for w in _words(option)}
    for entry in hints.get("items", {}).values():
        vocab |= {_stem(w) for w in _words(entry.get("family") or "")}
    for entry in hints.get("off_menu", []):
        vocab |= {_stem(w) for w in _words(entry["request"])}
    vocab -= {"a", "an", "the", "and", "with", "on", "of", "no", "extra", "regular", "plain"}
    location_words = {_stem(w) for loc in locations for w in _words(loc)}
    return vocab, location_words


def anchors(text, vocab, locations):
    stems = [_stem(w) for w in _words(text)]
    found = {s for s in stems if s in vocab}
    found |= {w for w in _words(text) if w in NUMBER_WORDS or w.isdigit()}
    # "no" changes meaning ("no onions"), so it must survive too.
    if "no" in _words(text):
        found.add("no")
    places = [loc for loc in locations if loc.lower() in text.lower()]
    return found, places


def acceptable(original, candidate, vocab, locations):
    if not candidate or len(candidate) > 2.2 * len(original) + 20 or "\n" in candidate.strip():
        return False
    need, places = anchors(original, vocab, locations)
    have, have_places = anchors(candidate, vocab, locations)
    return need == have and sorted(places) == sorted(have_places)


def call(model, text, seed, url="http://localhost:11434/api/chat"):
    body = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT.format(text=text)}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0.8, "seed": seed, "num_predict": 120},
    }
    request = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=120) as response:
        content = json.loads(response.read())["message"]["content"]
    return content.strip().strip('"').strip()


def paraphrase_rows(rows, model, vocab, locations, rng, share=0.5, tries=2, log=print):
    stats = {"tried": 0, "kept": 0}
    for row in rows:
        targets = [("initial_utterance", None)]
        targets += [("clarification_replies", i) for i, r in enumerate(row["clarification_replies"]) if len(r.split()) >= 4]
        for field, index in targets:
            if rng.random() >= share:
                continue
            original = row[field] if index is None else row[field][index]
            stats["tried"] += 1
            for attempt in range(tries):
                candidate = call(model, original, seed=rng.randrange(1 << 30))
                if acceptable(original, candidate, vocab, locations):
                    if index is None:
                        row[field] = candidate
                    else:
                        row[field][index] = candidate
                    row.setdefault("paraphrased", []).append(field if index is None else f"reply{index}")
                    stats["kept"] += 1
                    break
        if stats["tried"] and stats["tried"] % 100 == 0:
            log(f"paraphrase: {stats['kept']}/{stats['tried']} kept")
    return stats
