# ntfy Bidirectional Question Answering

**Plan ID**: 260208NB  
**Status**: Active  
**Created**: 2026-02-08

## Objective

Enable agents to receive question answers directly via ntfy replies, eliminating the need for SSH access.

## Current Flow (One-Way)
```
Agent asks question → ntfy push → User sees on phone → SSH in → CLI answer
```

## New Flow (Bidirectional)
```
Agent asks question → ntfy push with question_id → User replies in ntfy app → Daemon polls ntfy → Auto-answers question
```

## Implementation

### Phase 1: ntfy Polling
- Add `poll_ntfy(topic, since)` to `utils/ntfy.py`
- Returns list of messages from topic since timestamp

### Phase 2: Reply Matching
- Include question_id in notification (e.g., in message footer)
- Parse ntfy replies to extract answer text
- Match replies to pending questions by timestamp correlation

### Phase 3: Integration
- Update question watcher to poll ntfy for replies
- Auto-answer questions when matching reply found
- Confirmation notification back to user

## Files to Modify

- `modules/AgenticCLI/src/agenticcli/utils/ntfy.py` - Add `poll_ntfy()`
- `modules/AgenticCLI/src/agenticcli/commands/question.py` - Integration
- `modules/AgenticCLI/src/agenticcli/services/question_watcher.py` - Poll loop
- `modules/AgenticCLI/tests/test_ntfy.py` - Unit tests
- `modules/AgenticCLI/tests/test_uat_phone_notifications.py` - UAT tests

## Success Criteria

- [ ] `poll_ntfy()` returns recent messages from topic
- [ ] Question notifications include question_id
- [ ] Watcher detects ntfy replies and matches to questions  
- [ ] Questions auto-answered from ntfy replies
- [ ] Confirmation notification sent after answer processed
