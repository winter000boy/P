"""Fine-tune a small DeBERTa classifier: SAFE (0) vs ATTACK (1, prompt injection or jailbreak)."""
import torch
from datasets import concatenate_datasets, load_dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
)

BASE_MODEL = "microsoft/deberta-v3-small"


def load_data():
    """deepset/prompt-injections (text, label) + jackhhao/jailbreak-classification (prompt, type)."""
    injections = load_dataset("deepset/prompt-injections")
    jailbreaks = load_dataset("jackhhao/jailbreak-classification").map(
        lambda x: {"text": x["prompt"], "label": int(x["type"] == "jailbreak")},
        remove_columns=["prompt", "type"],
    )
    return {s: concatenate_datasets([injections[s], jailbreaks[s]]).shuffle(seed=42) for s in ("train", "test")}


if __name__ == "__main__":
    tok = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL,
        dtype=torch.float32,  # the checkpoint is stored as fp16; training in fp16 without loss scaling goes NaN
        num_labels=2,
        id2label={0: "SAFE", 1: "ATTACK"},
        label2id={"SAFE": 0, "ATTACK": 1},
    )
    train = load_data()["train"].map(lambda b: tok(b["text"], truncation=True, max_length=256), batched=True)

    args = TrainingArguments(
        output_dir="checkpoints",
        num_train_epochs=3,
        per_device_train_batch_size=16,
        learning_rate=3e-5,
        warmup_steps=0.1,  # float < 1 = ratio of total steps
        save_strategy="no",
        logging_steps=20,
        report_to="none",
        seed=42,
    )
    Trainer(model=model, args=args, train_dataset=train, data_collator=DataCollatorWithPadding(tok)).train()
    model.save_pretrained("model")
    tok.save_pretrained("model")
    print("Saved classifier to ./model - now run: python evaluate.py")
