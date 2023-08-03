# -*- coding: utf-8 -*-
"""Untitled4 (3).ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1IU54iQBKZc3-72TeNWEcZH8AE9H9zv-p
"""

import pandas as pd
import numpy as np

# pip install transformers[sentencepiece] datasets sacrebleu rouge_score py7zr -q

# nvidia-smi

from transformers import pipeline, set_seed, AutoModelForSeq2SeqLM, AutoTokenizer
import matplotlib.pyplot as plt
from datasets import load_dataset, load_metric
import nltk
from nltk.tokenize import sent_tokenize
from tqdm import tqdm
import torch

nltk.download("punkt")

device = "cuda" if torch.cuda.is_available() else "cpu"
device

model_ckpt ="google/pegasus-cnn_dailymail"
tokenizer = AutoTokenizer.from_pretrained(model_ckpt)

model_pegasus = AutoModelForSeq2SeqLM.from_pretrained(model_ckpt).to(device)

load_samsum_dataset = load_dataset("samsum")
load_samsum_dataset

"""// to find the length of the dataset, for training, testing and validation of the model."""

split_lengths = [len(load_samsum_dataset[split]) for split in load_samsum_dataset]
split_lengths

print(f"Features: {load_samsum_dataset['train'].column_names}")

print("\nDialogue:")
print(load_samsum_dataset["test"][1]["dialogue"])
print("\nSummary:")
print(load_samsum_dataset["test"][1]["summary"])

dialogue = load_samsum_dataset['test'][0]['dialogue']
dialogue

pipe = pipeline('summarization', model = model_ckpt)

pipe_out = pipe(dialogue)
pipe_out

print(pipe_out[0]['summary_text'].replace(" .<n>",".\n"))

def generate_batch_sized_chunks(list_of_elements, batch_size):
    """split the dataset into smaller batches that we can process simultaneously
    Yield successive batch-sized chunks from list_of_elements."""
    for i in range(0, len(list_of_elements), batch_size):
        yield list_of_elements[i : i + batch_size]

def calculate_metric_on_test_ds(dataset, metric, model, tokenizer,
                               batch_size=16, device=device,
                               column_text="article",
                               column_summary="highlights"):
    article_batches = list(generate_batch_sized_chunks(dataset[column_text], batch_size))
    target_batches = list(generate_batch_sized_chunks(dataset[column_summary], batch_size))

    for article_batch, target_batch in tqdm(
        zip(article_batches, target_batches), total=len(article_batches)):

        inputs = tokenizer(article_batch, max_length=1024,  truncation=True,
                        padding="max_length", return_tensors="pt")

        summaries = model.generate(input_ids=inputs["input_ids"].to(device),
                         attention_mask=inputs["attention_mask"].to(device),
                         length_penalty=0.8, num_beams=8, max_length=128)
        ''' parameter for length penalty ensures that the model does not generate sequences that are too long. '''

        # Finally, we decode the generated texts,
        # replace the  token, and add the decoded texts with the references to the metric.
        decoded_summaries = [tokenizer.decode(s, skip_special_tokens=True,
                                clean_up_tokenization_spaces=True)
               for s in summaries]

        decoded_summaries = [d.replace("", " ") for d in decoded_summaries]


        metric.add_batch(predictions=decoded_summaries, references=target_batch)

    #  Finally compute and return the ROUGE scores.
    score = metric.compute()
    return score

rouge_matric = load_metric('rouge')

score = calculate_metric_on_test_ds(load_samsum_dataset['test'], rouge_matric, model_pegasus, tokenizer, column_text = 'dialogue', column_summary = 'summary', batch_size = 8)

# rouge_names = ['rouge1','rouge2','rougeL','rougeLsum']
# rouge_dict = dict((rn, score[rn].mid.fmeasure ) for rn in rouge_names )

# pd.DataFrame(rouge_dict, index = ['pegasus'])

rouge_names = ["rouge1", "rouge2", "rougeL", "rougeLsum"]
rouge_dict = dict((rn, score[rn].mid.fmeasure ) for rn in rouge_names )

pd.DataFrame(rouge_dict, index = ['pegasus'])

def convert_examples_to_features(example_batch):
    input_encodings = tokenizer(example_batch['dialogue'] , max_length = 1024, truncation = True )

    with tokenizer.as_target_tokenizer():
        target_encodings = tokenizer(example_batch['summary'], max_length = 128, truncation = True )

    return {
        'input_ids' : input_encodings['input_ids'],
        'attention_mask': input_encodings['attention_mask'],
        'labels': target_encodings['input_ids']
    }

dataset_samsum_pt = load_samsum_dataset.map(convert_examples_to_features, batched = True)

dataset_samsum_pt['train'][0]

from transformers import DataCollatorForSeq2Seq

seq2seq_data_collator = DataCollatorForSeq2Seq(tokenizer, model = model_pegasus)

# pip install accelerate -U

# from google.colab import drive
# drive.mount('/content/drive')

from transformers import TrainingArguments, Trainer

trainer_args = TrainingArguments(
    output_dir='pegasus-samsum', num_train_epochs=1, warmup_steps=500,
    per_device_train_batch_size=1, per_device_eval_batch_size=1,
    weight_decay=0.01, logging_steps=10,
    evaluation_strategy='steps', eval_steps=500, save_steps=1e6,
    gradient_accumulation_steps=16
)

# %cd /content/drive/MyDrive/

trainer = Trainer(model=model_pegasus, ags=trainer_args,
                  tokenizer = tokenizer, data_collator = seq2seq_data_collator,
                  train_dataset = dataset_samsum_pt["train"],
                  eval_dataset = dataset_samsum_pt["validation"])

trainer.train()

model_pegasus.save_pretrained("Data-Abstraction")

tokenizer.save_pretrained("tokenizer")

# Inferencing

from google.colab import drive
drive.mount('/content/drive')

# = load_dataset("samsum")

split_lengths = [len(dataset_samsum[split])for split in dataset_samsum]

print(f"Split lengths: {split_lengths}")
print(f"Features: {dataset_samsum['train'].column_names}")
print("\nDialogue:")

print(dataset_samsum["test"][1]["dialogue"])

print("\nSummary:")

print(dataset_samsum["test"][1]["summary"])