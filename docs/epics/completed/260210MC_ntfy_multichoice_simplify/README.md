# Plan: ntfy Multi-Choice Support and Notification Simplification

**Plan ID**: 260210MC_ntfy_multichoice_simplify
**Status**: Planning
**Created**: 2026-02-10
**Target Project**: /home/code/AgenticEngineering

## Objective

Simplify the ntfy question notification system and add multi-choice answer support to improve the phone-based question answering experience.

### Changes

1. **Remove Severity Gating**: All questions now trigger push notifications regardless of severity level (blocking/high/medium/low). Previously only blocking/high severity questions notified.

2. **Multi-Choice Formatting**: Questions with `suggested_answers` now display as lettered options (A/B/C/D) in the notification body for easy selection.

3. **Letter Reply Parsing**: When users reply with a single letter (A-J, case-insensitive), the system maps it to the corresponding suggested answer text before saving.

4. **Backward Compatibility**: Free-text replies continue to work as before. The system only applies letter mapping when the reply is a single letter.

## Key Features

### Before
```
Medium severity question created → No notification sent
Question with suggestions → Plain text notification
Phone reply "A" → Saved literally as "A"
```

### After
```
Medium severity question created → Push notification sent
Question with suggestions → Formatted with A) B) C) options
Phone reply "A" → Mapped to first suggested answer text
```

## Example Notification

```
Which database for caching?

A) Redis
B) PostgreSQL
C) SQLite
D) None - use in-memory only

[QID: Q-20260210-075329-a62a]
```

User can reply with just "B" and the system will save "PostgreSQL" as the answer.

## Implementation Phases

### Phase 1: Build (3 tasks)
- Remove severity gate in `_send_ntfy_if_configured()`
- Add multi-choice formatting in `notify_new_question()`
- Add letter parsing in `NtfyReplyPoller`

### Phase 2: Test (4 tasks)
- Update/remove severity gating tests
- Add multi-choice formatting tests
- Add letter reply parsing tests
- Update UAT end-to-end tests

## Files Modified

1. `modules/AgenticCLI/src/agenticcli/commands/question.py` - Remove severity gate
2. `modules/AgenticCLI/src/agenticcli/utils/ntfy.py` - Add letter formatting
3. `modules/AgenticCLI/src/agenticcli/services/question_watcher.py` - Add letter parsing
4. `modules/AgenticCLI/tests/test_ntfy.py` - Update unit tests
5. `modules/AgenticCLI/tests/test_uat_e2e_notification_flow.py` - Update UAT tests

## Success Criteria

- All severity levels trigger notifications (verified by tests)
- Multi-choice questions show lettered options in notification body
- Letter replies (A-J) map to corresponding suggested_answer text
- Free-text replies continue to work (backward compatibility)
- All existing tests pass after updates
- New tests verify multi-choice formatting and letter parsing
- UAT tests verify complete user journey

## User Acceptance Testing

1. **All Questions Notify**: Create medium severity question, verify phone notification received
2. **Multi-Choice Display**: Create question with 3 suggestions, verify A/B/C options shown
3. **Letter Reply Mapping**: Reply with 'B', verify answer saved as mapped option text
4. **Free Text Fallback**: Reply with custom text, verify full text saved as answer

## Dependencies

- Existing ntfy infrastructure (topic configuration, poll/send functions)
- Existing question model with `suggested_answers` field
- Existing `NtfyReplyPoller` daemon thread architecture

## Risk Mitigation

- Graceful fallback: Letter mapping failures fall back to original reply text
- Validation: Max 10 options (A-J) prevents abuse
- Testing: Comprehensive unit and UAT coverage for edge cases
- Backward compatibility: No breaking changes to existing workflows

## Notes

- Severity remains in the model for UI display and filtering purposes
- Letter format limited to A-J (max 10 options) for usability
- Case-insensitive letter matching for better UX
- Multi-word replies like "A is best" treated as free text, not mapped
