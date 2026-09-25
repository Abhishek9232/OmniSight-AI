-- =============================================================================
-- OmniSight-AI Database Schema
-- Database: omnisight_ai
-- Description: DDL schema definition for recreating the OmniSight-AI database.
-- =============================================================================

CREATE DATABASE IF NOT EXISTS omnisight_ai;
USE omnisight_ai;

-- -----------------------------------------------------------------------------
-- 1. Users Table
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('student', 'teacher', 'admin') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 2. Exams Table
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS exams (
    exam_id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT NULL,
    duration_minutes INT NOT NULL,
    created_by INT NOT NULL,
    status VARCHAR(30) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_exams_created_by FOREIGN KEY (created_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 3. Questions Table
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS questions (
    question_id INT AUTO_INCREMENT PRIMARY KEY,
    exam_id INT NOT NULL,
    question_text TEXT NOT NULL,
    option_a VARCHAR(500) NOT NULL,
    option_b VARCHAR(500) NOT NULL,
    option_c VARCHAR(500) NOT NULL,
    option_d VARCHAR(500) NOT NULL,
    correct_option CHAR(1) NOT NULL,
    marks INT NOT NULL DEFAULT 1,
    CONSTRAINT fk_questions_exam_id FOREIGN KEY (exam_id) REFERENCES exams(exam_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 4. Exam Attempts Table
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS exam_attempts (
    attempt_id INT AUTO_INCREMENT PRIMARY KEY,
    exam_id INT NOT NULL,
    student_id INT NOT NULL,
    started_at DATETIME NOT NULL,
    submitted_at DATETIME NULL,
    status VARCHAR(30) NOT NULL,
    CONSTRAINT fk_exam_attempts_exam_id FOREIGN KEY (exam_id) REFERENCES exams(exam_id),
    CONSTRAINT fk_exam_attempts_student_id FOREIGN KEY (student_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 5. Answers Table
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS answers (
    answer_id INT AUTO_INCREMENT PRIMARY KEY,
    attempt_id INT NOT NULL,
    question_id INT NOT NULL,
    selected_option VARCHAR(1) NULL,
    is_correct BOOLEAN NULL,
    answered_at DATETIME NULL,
    CONSTRAINT fk_answers_attempt_id FOREIGN KEY (attempt_id) REFERENCES exam_attempts(attempt_id),
    CONSTRAINT fk_answers_question_id FOREIGN KEY (question_id) REFERENCES questions(question_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 6. Results Table
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS results (
    result_id INT AUTO_INCREMENT PRIMARY KEY,
    attempt_id INT NOT NULL UNIQUE,
    total_marks DECIMAL(7,2) NOT NULL,
    obtained_marks DECIMAL(7,2) NOT NULL,
    percentage DECIMAL(5,2) NULL,
    evaluated_at DATETIME NOT NULL,
    CONSTRAINT fk_results_attempt_id FOREIGN KEY (attempt_id) REFERENCES exam_attempts(attempt_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 7. Monitoring Events Table
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS monitoring_events (
    event_id INT AUTO_INCREMENT PRIMARY KEY,
    attempt_id INT NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    event_timestamp DATETIME NOT NULL,
    event_metadata JSON NULL,
    CONSTRAINT fk_monitoring_events_attempt_id FOREIGN KEY (attempt_id) REFERENCES exam_attempts(attempt_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 8. Behavioral Features Table
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS behavioral_features (
    feature_id INT AUTO_INCREMENT PRIMARY KEY,
    attempt_id INT NOT NULL,
    feature_name VARCHAR(100) NOT NULL,
    feature_value DECIMAL(12,4) NOT NULL,
    generated_at DATETIME NOT NULL,
    CONSTRAINT fk_behavioral_features_attempt_id FOREIGN KEY (attempt_id) REFERENCES exam_attempts(attempt_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 9. Integrity Assessments Table
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS integrity_assessments (
    assessment_id INT AUTO_INCREMENT PRIMARY KEY,
    attempt_id INT NOT NULL,
    risk_score DECIMAL(6,3) NULL,
    risk_category VARCHAR(30) NULL,
    model_name VARCHAR(100) NULL,
    assessment_metadata JSON NULL,
    created_at DATETIME NOT NULL,
    CONSTRAINT fk_integrity_assessments_attempt_id FOREIGN KEY (attempt_id) REFERENCES exam_attempts(attempt_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
