# Dialogue Dataset Format

Do not commit raw participant transcripts or identifiable student information. Use consented, de-identified and project-approved data; synthetic examples can be used while the annotation protocol is being developed. Keep the frozen menu snapshot used to annotate the data with the dataset version.

Each line in the input JSONL to `split_dialogue_dataset` is one complete dialogue:

```json
{
  "dialogue_id": "dialogue-0001",
  "category": "omitted_location",
  "source_group": "participant-or-generation-batch-07",
  "initial_utterance": "One veggie wrap, please",
  "clarification_replies": ["Deliver it to the Main Library"],
  "gold_order": {
    "vendor_id": 4,
    "delivery_location": "Main Library",
    "items": [
      {
        "menu_item_id": "12",
        "quantity": 1,
        "customizations": []
      }
    ]
  }
}
```

`source_group` identifies the participant, source conversation, or synthetic-generation batch. All dialogues from a source group are assigned to the same split. `category` is a stable annotation category (for example, omitted location, ambiguous item, quantity correction, required option, or complete order). `clarification_replies` are provided in order and are consumed only when the simulated assistant asks. `gold_order` uses IDs from the frozen menu snapshot; `vendor_id` is optional, but recommended. Items should use menu item IDs, positive integer quantities, and customization option names exactly as shown in the snapshot.

Before splitting, agree on an annotation guide with examples for item identity, quantity, customizations, location, and what counts as a correct final order. The experiment runner labels a turn `wrong` when its current draft does not exactly match the dialogue's gold order. It writes feature-only JSONL for each C1-C5 policy; it does not include transcript text in those feature files. Training should use only the training split, threshold/model selection only the validation split, and final reporting only the held-out test split.

The split ratio is approximately 60/20/20 by source group and category. Group constraints take precedence, so actual proportions may differ. Report the actual counts and categories per split rather than claiming exact ratios.
