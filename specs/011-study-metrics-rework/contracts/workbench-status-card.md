# Contract: Workbench Status Card

## Displayed Rows

The expanded workbench status card shows only these metric rows:

- 网页驻留
- 视频观看
- 复述点录入
- 复习用时
- AI 问答
- 走神时间

The collapsed summary uses web presence as the headline metric.

## Removed Rows

The card no longer shows these legacy rows:

- 有效学习时长
- 学习驻留
- 客观专注率
- 内容接触
- 复述点构建
- 录入复述点数
- 复习复述点数

Counts may appear in another product surface, but they are not part of this work status metric card.

## Arithmetic Invariant

For the displayed scope:

```text
网页驻留 = 视频观看 + 复述点录入 + 复习用时 + AI 问答 + 走神时间
```

The card must not display a set of values that violates this invariant.

## Empty State

If no web presence exists for the scope:

- Web presence shows `0m`.
- All category rows show `0m`.
- No focus-rate or effective-learning percentage is shown.

## Pomodoro Independence

Pomodoro scheduled focus time must not increase web presence or any card category unless the learner is actually web-present in the relevant state.
