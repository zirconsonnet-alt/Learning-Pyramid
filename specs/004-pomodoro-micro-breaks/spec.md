# Feature Specification: Pomodoro Random Micro Breaks

**Feature Branch**: `004-pomodoro-micro-breaks`  
**Created**: 2026-05-04  
**Status**: Draft  
**Input**: User description: "新增“随机微休息”学习模式：用户开始学习后，系统在设定时间范围内随机触发提醒，例如每 3–5 分钟一次；提醒触发时响铃，暂停视频播放，引导用户闭眼休息 10 秒，倒计时结束后自动回到学习状态，视频继续播放(如果之前在播放)。用户可自定义随机提醒间隔、微休息时长。时长从用户在工作台进入播放器全屏后开始计时，退出全屏会重置计时。该功能不能和学习结束10s前的提示相冲突，在学习时间结束前3分钟内不能触发。补充：这是番茄钟附带功能，开启番茄钟才能用，并且在番茄钟设置里开关或设置。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Enable Random Micro Breaks During Pomodoro Fullscreen Study (Priority: P1)

As a learner using a Pomodoro study session, I want random micro break reminders while watching course videos in fullscreen so that I can rest my eyes briefly without manually tracking time.

**Why this priority**: This is the core value of the feature: the learner gets automatic eye-rest guidance only during focused Pomodoro study.

**Independent Test**: Can be fully tested by enabling random micro breaks in Pomodoro settings, starting a Pomodoro learning segment, entering the workbench video fullscreen, and observing a reminder within the configured interval.

**Acceptance Scenarios**:

1. **Given** random micro breaks are enabled with a 3-5 minute interval and a 10-second rest duration, a Pomodoro learning segment is active, and the learner enters video fullscreen, **When** the randomized interval elapses outside the final 3 minutes of the learning segment, **Then** the system plays a reminder sound, pauses the video, shows a 10-second closed-eye rest countdown, and returns to learning when the countdown ends.
2. **Given** the video was playing when the micro break reminder triggered, **When** the countdown ends, **Then** the video resumes playback automatically.
3. **Given** the video was already paused when the micro break reminder triggered, **When** the countdown ends, **Then** the video remains paused and the learner returns to the normal study view.

---

### User Story 2 - Configure Micro Break Preferences In Pomodoro Settings (Priority: P2)

As a learner, I want to turn random micro breaks on or off and choose the random interval range and break duration in Pomodoro settings so that the reminders match my study rhythm.

**Why this priority**: The feature must be user-controlled because random interruptions can be helpful for some study sessions and distracting for others.

**Independent Test**: Can be tested by changing the Pomodoro setting values before a Pomodoro learning segment, then confirming the next fullscreen study session uses those values.

**Acceptance Scenarios**:

1. **Given** the learner opens Pomodoro settings, **When** they enable random micro breaks and set a minimum interval, maximum interval, and rest duration, **Then** the values are accepted only if the minimum interval is positive, the maximum interval is not less than the minimum, and the rest duration is positive.
2. **Given** random micro breaks are disabled in Pomodoro settings, **When** a Pomodoro learning segment is active and the learner enters video fullscreen, **Then** no random micro break reminder is scheduled or shown.
3. **Given** random micro breaks were configured previously, **When** the learner opens Pomodoro settings again, **Then** the previously chosen values are still shown.

---

### User Story 3 - Avoid End-Of-Study Conflicts And Fullscreen Resets (Priority: P3)

As a learner, I want random micro breaks to respect Pomodoro end timing and fullscreen state so that they do not interrupt the study-ending prompt or continue after I leave fullscreen.

**Why this priority**: The feature must cooperate with existing Pomodoro flow; reminders near the end of a learning segment would feel noisy and conflict with the existing final countdown prompt.

**Independent Test**: Can be tested by using a short remaining learning window, entering and exiting fullscreen, and confirming reminders are skipped or reset according to the timing rules.

**Acceptance Scenarios**:

1. **Given** a Pomodoro learning segment has 3 minutes or less remaining, **When** the random reminder interval would otherwise elapse, **Then** no micro break reminder triggers.
2. **Given** the existing learning-end prompt is due 10 seconds before the segment ends, **When** random micro breaks are enabled, **Then** no random micro break reminder overlaps with or replaces that learning-end prompt.
3. **Given** a learner exits video fullscreen before the randomized interval elapses, **When** they later re-enter fullscreen during the same Pomodoro learning segment, **Then** the random micro break timer starts over from the new fullscreen entry time.
4. **Given** a micro break countdown is visible, **When** the learner exits fullscreen, stops the Pomodoro, or leaves the workbench, **Then** the countdown is canceled and the video is not auto-resumed by the canceled micro break.

### Edge Cases

- If no Pomodoro learning segment is active, the feature remains unavailable and does not trigger from normal video fullscreen usage.
- If the Pomodoro is in a break phase, paused, completed, or stopped, random micro breaks do not trigger.
- If the learner enters fullscreen with less than the configured minimum interval remaining before the final 3-minute forbidden window, no reminder is scheduled for that fullscreen session.
- If a randomized trigger time would land inside the final 3-minute forbidden window, that reminder is skipped rather than moved earlier into the study period.
- If the browser or device cannot play the reminder sound, the visible rest prompt and countdown still appear.
- If the selected study item has no playable video, no micro break timer starts.
- If the learner changes settings while a fullscreen timer is already running, the new settings apply the next time the timer is scheduled or reset.
- Only one micro break reminder can be active at a time.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST expose random micro break controls in Pomodoro settings, including an enable/disable control, a minimum random interval, a maximum random interval, and a micro break duration.
- **FR-002**: System MUST keep random micro breaks disabled unless the learner has explicitly enabled them in Pomodoro settings.
- **FR-003**: System MUST allow random micro breaks to run only during an active Pomodoro learning segment.
- **FR-004**: System MUST start the random micro break timer only when the learner enters the workbench video player fullscreen during an eligible Pomodoro learning segment.
- **FR-005**: System MUST reset the random micro break timer whenever the learner exits video fullscreen.
- **FR-006**: System MUST choose each reminder delay randomly within the learner's configured minimum and maximum interval range.
- **FR-007**: System MUST schedule a new randomized interval after each completed micro break while the learner remains in an eligible fullscreen Pomodoro learning state.
- **FR-008**: System MUST NOT trigger a random micro break during the final 3 minutes of a Pomodoro learning segment.
- **FR-009**: System MUST NOT allow a random micro break reminder to overlap with, replace, or delay the existing learning-end prompt that appears 10 seconds before the learning segment ends.
- **FR-010**: System MUST skip a random micro break if its randomized trigger time would occur after the start of the final 3-minute forbidden window.
- **FR-011**: System MUST play an audible reminder when a random micro break triggers, unless the user's browser or device prevents sound playback.
- **FR-012**: System MUST pause the current video when a random micro break triggers.
- **FR-013**: System MUST remember whether the video was playing immediately before the random micro break paused it.
- **FR-014**: System MUST show a visible micro break state that instructs the learner to close their eyes and displays the remaining countdown.
- **FR-015**: System MUST automatically return to the normal learning state when the micro break countdown ends.
- **FR-016**: System MUST resume video playback after the countdown only if the video was playing immediately before the micro break triggered.
- **FR-017**: System MUST leave the video paused after the countdown if the video was already paused immediately before the micro break triggered.
- **FR-018**: System MUST cancel any pending or active random micro break when the Pomodoro leaves the learning phase, the Pomodoro stops, the learner exits fullscreen, or the learner leaves the workbench.
- **FR-019**: System MUST validate settings so the minimum interval is positive, the maximum interval is positive and not less than the minimum interval, and the micro break duration is positive.
- **FR-020**: System MUST preserve the learner's random micro break settings for future Pomodoro sessions.

### Key Entities

- **Random Micro Break Settings**: The learner's Pomodoro-level preference containing enabled state, minimum interval, maximum interval, and micro break duration.
- **Random Micro Break Timer**: The current fullscreen-session timing state, including the randomized target trigger time and eligibility based on Pomodoro learning phase and fullscreen state.
- **Micro Break Session**: A triggered rest event that records the pre-break playback state, countdown duration, and completion or cancellation outcome.
- **Pomodoro Learning Segment**: The active study period that defines whether random micro breaks are eligible and when the final 3-minute forbidden window begins.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of random micro break reminders trigger only while a Pomodoro learning segment is active and the learner is in video fullscreen.
- **SC-002**: 0 random micro break reminders trigger during the final 3 minutes of a Pomodoro learning segment or during the existing 10-second learning-end prompt.
- **SC-003**: In eligible fullscreen study time, each reminder trigger occurs within the learner's configured minimum and maximum interval range, excluding sessions that enter the final 3-minute forbidden window first.
- **SC-004**: When a reminder triggers, the video is paused and the visible rest countdown appears within 1 second.
- **SC-005**: After the countdown ends, the system restores the correct playback state within 1 second: playing videos resume and previously paused videos stay paused.
- **SC-006**: A learner can enable the feature and set interval and duration preferences from Pomodoro settings in under 1 minute.
- **SC-007**: Exiting fullscreen before a reminder triggers resets the timer in 100% of observed sessions.

## Assumptions

- The default random interval range is 3-5 minutes because the user provided it as the primary example.
- The default micro break duration is 10 seconds because the user described a 10-second closed-eye rest.
- Random micro breaks are off by default so existing Pomodoro study behavior remains unchanged until the learner opts in.
- Settings belong to the Pomodoro feature, not to individual videos, projects, or normal non-Pomodoro workbench playback.
- "Learning time ends" refers to the active Pomodoro learning segment's scheduled end time.
