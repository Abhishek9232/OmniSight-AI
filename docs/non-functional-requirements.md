# Non-Functional Requirements

## 1. Usability

* The system should provide a simple and understandable interface for both teachers and students.
* Examination-related actions should be clearly visible and easy to access.
* The monitoring and result information presented to teachers should be understandable without requiring technical knowledge of the underlying machine-learning models.

## 2. Performance

* The system should provide responsive interaction during normal examination activities.
* Examination questions and submitted answers should be processed without unnecessary delay.
* Monitoring events should be recorded without significantly disrupting the examination experience.
* Dashboard visualizations should load within a reasonable time for the academic prototype's expected dataset size.

## 3. Reliability

* The system should maintain consistent examination state during an active examination.
* Submitted answers should not be unintentionally lost during normal operation.
* Monitoring and examination events should be stored consistently.
* The system should handle expected application errors without corrupting stored examination data.

## 4. Security

* User authentication should be required for protected system functionality.
* Role-based access should prevent students from accessing teacher-specific functionality.
* Sensitive configuration information, such as database credentials, should not be hard-coded in source code.
* User and examination data should be protected from unauthorized application-level access.
* AI-generated integrity assessments should not directly trigger disciplinary actions.

## 5. Maintainability

* The application should use a clear and modular project structure.
* Components should have well-defined responsibilities.
* Configuration should be separated from application logic where appropriate.
* Code should be documented sufficiently to support future development and debugging.
* Machine-learning components should be designed so that baseline models can be evaluated or replaced without unnecessarily modifying unrelated application components.

## 6. Scalability

* The system should use a database structure capable of storing data for multiple examinations and students within the expected academic prototype scope.
* The application structure should allow additional features to be introduced without requiring a complete redesign.
* Scalability beyond the academic prototype is not a primary requirement of the initial MVP.

## 7. Explainability

* Integrity-risk results should be accompanied by relevant supporting evidence where available.
* The system should preserve the events and features used for integrity analysis.
* The dashboard should allow a teacher to understand the basis of an integrity-risk assessment.
* The system should avoid presenting an automated risk assessment as a definitive determination of misconduct.

## 8. Data Integrity

* Examination answers should be associated with the correct student and examination.
* Monitoring events should contain sufficient contextual information, including timestamps where applicable.
* Stored results should remain consistent with the submitted examination data.
* Feature-generation processes should use identifiable source data so that analysis can be traced back to the relevant examination events.

## 9. Compatibility

* The application should operate in the development environment defined for the project.
* The web interface should work with commonly used modern browsers available in the intended academic testing environment.
* The system should use the selected project technology stack consistently.

## 10. Testability

* Major application components should be testable independently where practical.
* Examination workflows should be tested using controlled scenarios.
* Monitoring functionality should be tested under different face-detection conditions.
* Machine-learning components should be evaluated using appropriate datasets and evaluation metrics.
* Integration testing should verify that examination, monitoring, database, analysis, and dashboard components work together correctly.

## 11. Academic Prototype Constraint

The non-functional requirements are defined for a final-year academic prototype rather than a production-scale commercial examination platform.

Therefore, the project prioritizes:

* Correctness of the demonstrated workflow.
* Clear architecture.
* Explainable analysis.
* Maintainable implementation.
* Reproducible testing.

Enterprise-scale availability, distributed infrastructure, and production-level scalability are outside the initial MVP.
