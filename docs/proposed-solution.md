# Proposed Solution

OmniSight-AI proposes an integrated online examination platform that combines examination management, basic AI-assisted monitoring, behavioral event logging, feature-based analysis, and an explainable integrity-risk assessment.

The system will provide an environment in which an instructor can create and manage examinations, while students can attempt examinations through a controlled online interface. During an examination, relevant monitoring and activity events will be recorded, such as candidate face presence, multiple-face detection, and selected examination activity events.

The collected events will be transformed into meaningful features that can be used for data analysis and machine-learning-based integrity-risk assessment. Instead of treating a single detected event as proof of misconduct, the system will consider multiple available signals and present the resulting assessment together with supporting evidence.

A teacher-oriented dashboard will provide examination results, integrity-risk information, and an event timeline so that the instructor can review the available evidence. The final interpretation of the evidence will remain with the human reviewer rather than being automatically treated as a definitive determination of misconduct.

The proposed solution therefore focuses on four major capabilities:

1. **Online Examination Management**
   Creation, management, delivery, timing, submission, and result handling of online examinations.

2. **AI-Assisted Monitoring**
   Basic computer-vision-based monitoring for selected examination events, such as face absence and multiple-face detection.

3. **Behavioral Evidence and Feature Analysis**
   Recording relevant examination events and transforming them into structured features for analysis.

4. **Explainable Integrity-Risk Assessment**
   Generating an integrity-risk assessment and presenting its contributing evidence through a teacher-oriented dashboard.

The initial implementation will remain an academic prototype. Advanced capabilities such as secure code execution, large-scale distributed infrastructure, complex deep-learning-based behavior analysis, and automated question generation are outside the initial project scope.
