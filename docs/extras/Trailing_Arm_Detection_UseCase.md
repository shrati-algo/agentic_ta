# Use Case Document
## Trailing Arm Detection
*Automated Defect Detection in Assembly Line Production*

---

## Document Control

| Field | Value |
|---|---|
| **Project Name** | Trailing Arm Detection |
| **Document Type** | Use Case Document |
| **Domain** | Manufacturing / Quality Inspection |
| **Technology** | Computer Vision, Image Processing |
| **Version** | 1.0 |
| **Status** | Draft |
| **Prepared For** | Assembly Line Quality Monitoring Team |

---

## 1. Executive Summary

The Trailing Arm Detection project aims to automate the defect detection process in an assembly line production system using computer vision. Currently, the inspection of trailing arm components — specifically the measurement of the innermost circle diameter — is performed manually by assembly line operators. This manual process is time-consuming, subject to human error, and creates bottlenecks in the production pipeline.

This project introduces an automated solution that ingests chassis images via an API-driven folder mechanism, applies computer vision algorithms to detect and measure the innermost circle on the trailing arm, and returns the measured diameter to the end users in real time. The solution is designed to reduce manual intervention, improve inspection consistency, and provide operators with a reliable tool to monitor product quality.

---

## 2. Business Problem

Manual defect detection on the assembly line, particularly for dimensional checks of the trailing arm's innermost circle, presents the following challenges:

- High dependency on operator skill and attention, leading to inconsistent measurements across shifts.
- Slow inspection cycle times that constrain overall assembly line throughput.
- Difficulty in traceability — measurement records tied to chassis numbers are often missing or incomplete.
- Increased risk of defective components passing to downstream assembly stages.
- Operator fatigue contributing to missed defects during long production shifts.

There is a clear business need to automate this measurement process to reduce manual intervention, improve accuracy, and enable real-time defect detection with full traceability to each chassis.

---

## 3. Project Objectives

1. Automate the measurement of the innermost circle diameter on the trailing arm using computer vision.
2. Eliminate manual dimensional inspection for this specific defect check.
3. Integrate seamlessly with existing assembly line systems through an API that provides chassis numbers and associated image folders.
4. Deliver measurement results with chassis-level traceability.
5. Provide operators with a simple interface to monitor produce in real time.
6. Reduce inspection time per component and improve overall production throughput.

---

## 4. Scope

### 4.1 In Scope
- Ingestion of trailing arm images from a designated folder associated with a chassis number.
- Detection of circular features on the trailing arm using computer vision.
- Measurement of the diameter of the innermost circle.
- API-based integration for chassis number input.
- Display of measured diameter to assembly line operators.
- Logging and storage of measurement results with chassis mapping.

### 4.2 Out of Scope
- Defect detection on components other than the trailing arm.
- Measurement of features other than the innermost circle diameter.
- Physical hardware installation (cameras, lighting, mounts) at the assembly line.
- Repair or rework decisions based on measurement outcomes.

---

## 5. Stakeholders

| Stakeholder | Role | Responsibility |
|---|---|---|
| Assembly Line Operators | End Users | Monitor the produce in real time using the measurement output to identify defective trailing arms. |
| Data Scientists | Data Owners | Develop, train, and maintain computer vision models; ensure measurement accuracy and reliability. |
| Frontend Developers | Data Providers / UI Owners | Deliver chassis data and images through the API, and maintain the user-facing interface for operators. |
| Quality Assurance Team | Secondary User | Audit measurement outcomes and validate system performance against manual benchmarks. |
| Production Managers | Business Sponsor | Oversee production throughput improvements and defect reduction metrics. |

---

## 6. Use Case Specification

| Attribute | Description |
|---|---|
| **Use Case ID** | UC-TAD-001 |
| **Use Case Name** | Measure Innermost Circle Diameter on Trailing Arm |
| **Primary Actor** | Assembly Line Operator |
| **Secondary Actors** | Chassis API System, Computer Vision Engine, Data Storage Layer |
| **Trigger** | A new chassis enters the inspection station and its chassis number is pushed through the API. |
| **Preconditions** | Chassis number received via API. Associated image folder exists and contains valid trailing arm images. Computer vision service is running. |
| **Postconditions** | Measured innermost circle diameter is returned, displayed to the operator, and logged against the chassis number. |
| **Frequency** | Every trailing arm processed on the assembly line. |

### 6.1 Main Flow (Basic Scenario)

1. The API system sends a chassis number to the detection service.
2. The service locates the image folder corresponding to the chassis number.
3. The service loads the trailing arm image(s) from the folder.
4. The computer vision model performs pre-processing on the image (noise reduction, contrast adjustment, region of interest extraction).
5. The model detects all circular features present on the trailing arm.
6. The algorithm identifies the innermost circle from the set of detected circles.
7. The system computes the diameter of the innermost circle and converts the measurement to engineering units (millimeters).
8. The measured diameter is returned to the frontend layer along with the chassis number.
9. The assembly line operator views the measurement on the monitoring interface.
10. The measurement result is persisted in the data store for traceability and auditing.

### 6.2 Alternative Flows

**AF-1: Image Folder Missing**
- If the folder for the chassis number is missing, the system logs the incident and notifies the operator to re-capture images.

**AF-2: No Circle Detected**
- If no circular feature can be identified, the system flags the chassis for manual inspection and records the failure reason.

**AF-3: Low-Confidence Measurement**
- If the measurement confidence score falls below the threshold, the system prompts the operator to validate the result manually.

**AF-4: Measurement Out of Tolerance**
- If the diameter falls outside the configured tolerance range, the system highlights the chassis as defective and alerts the operator.

---

## 7. Functional Requirements

| ID | Requirement |
|---|---|
| FR-01 | The system shall receive a chassis number from an external API. |
| FR-02 | The system shall access a predefined folder structure to load images associated with the chassis number. |
| FR-03 | The system shall apply image pre-processing steps to enhance feature detection. |
| FR-04 | The system shall detect circular features on the trailing arm using computer vision techniques. |
| FR-05 | The system shall identify the innermost circle from the detected features. |
| FR-06 | The system shall measure the diameter of the innermost circle in millimeters. |
| FR-07 | The system shall return the measured diameter along with the chassis number. |
| FR-08 | The system shall display the measurement to the assembly line operator via a frontend interface. |
| FR-09 | The system shall persist every measurement with a timestamp and chassis mapping. |
| FR-10 | The system shall allow configuration of tolerance thresholds for pass/fail decisions. |

---

## 8. Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Performance** | Measurement shall be completed within a defined cycle time to match assembly line pace. |
| **Accuracy** | Measurement accuracy shall be within acceptable engineering tolerances validated against manual measurements. |
| **Availability** | The system shall be available during all production shifts with minimal downtime. |
| **Reliability** | The solution shall produce consistent results across different lighting and positioning conditions. |
| **Scalability** | The architecture shall support future expansion to additional components or measurement types. |
| **Usability** | The frontend shall provide an intuitive interface that requires minimal training for operators. |
| **Traceability** | Every measurement shall be linked to a unique chassis number and stored for audit purposes. |
| **Maintainability** | The computer vision model shall be retrainable with new data as the product evolves. |

---

## 9. Input and Output Specification

### 9.1 Inputs
- Chassis number provided by the production API.
- Folder containing trailing arm images associated with the chassis number.
- Configuration parameters such as tolerance thresholds and camera calibration values.

### 9.2 Outputs
- Measured diameter of the innermost circle on the trailing arm (in millimeters).
- Chassis number to which the measurement corresponds.
- Measurement status indicator (within tolerance / out of tolerance / requires manual review).
- Timestamp of measurement.
- Audit log entry persisted for traceability.

---

## 10. Solution Workflow

The end-to-end workflow of the Trailing Arm Detection system is described below:

1. Chassis arrives at the inspection station and the production API emits the chassis number.
2. The system locates the corresponding image folder for the chassis.
3. Images are loaded and pre-processed to prepare them for analysis.
4. The computer vision model detects circular features on the trailing arm.
5. The innermost circle is selected from the detected set.
6. Its diameter is measured and validated against tolerance rules.
7. Results are pushed to the frontend interface for operator monitoring.
8. Measurement records are stored for reporting and future model training.

---

## 11. Success Criteria and KPIs

- Significant reduction in manual inspection effort for trailing arm dimensional checks.
- Measurement accuracy comparable to or better than manual inspection benchmarks.
- Complete traceability with every chassis linked to a measurement record.
- Improved assembly line throughput attributable to faster inspection cycles.
- Reduction in defective trailing arms passing downstream.
- Positive operator adoption and feedback on the monitoring interface.

---

## 12. Assumptions and Constraints

### 12.1 Assumptions
- The API will consistently deliver a valid chassis number for every component inspected.
- Images captured for each chassis will be of sufficient quality and angle for circle detection.
- Camera calibration and environmental lighting will remain within an acceptable operating envelope.
- Ground-truth measurement data will be available for model training and validation.

### 12.2 Constraints
- The solution must operate within the cycle-time limits of the assembly line.
- The system must integrate with the existing chassis-numbering and image-capture infrastructure.
- Any frontend interface must be usable by operators without specialized data-science knowledge.

---

## 13. Risks and Mitigation

| Risk | Impact | Mitigation |
|---|---|---|
| Poor image quality reducing detection accuracy | High | Establish image-quality checks; alert when inputs fall below quality threshold. |
| Variation in lighting conditions on the line | Medium | Apply adaptive pre-processing; define acceptable lighting envelope. |
| Model drift over time as products evolve | Medium | Schedule periodic retraining with newly collected data. |
| Operator mistrust of automated output | Medium | Provide transparent confidence scores; allow manual override for flagged cases. |
| API delivering incorrect chassis-to-image mappings | High | Implement validation checks on chassis-folder correspondence before processing. |
| Edge cases not represented in training data | Medium | Flag low-confidence cases for manual review and feed them back into training. |

---

## 14. Expected Benefits

- Drastic reduction in manual intervention for trailing arm inspection.
- Consistent, objective measurement results independent of operator skill.
- Faster feedback loop to identify and correct defects early.
- Digital traceability enabling data-driven quality improvements.
- A reusable platform that can be extended to other components and measurements in the future.
- Cost savings through reduced rework and improved first-pass yield.

---

## 15. Conclusion

The Trailing Arm Detection project addresses a clear operational pain point by replacing manual dimensional inspection with an automated computer vision solution. By tying every measurement to a chassis number delivered through the API, the system provides end-to-end traceability while freeing assembly line operators from repetitive inspection tasks. The resulting gains in accuracy, throughput, and data availability position the project as a foundational step toward a broader vision-based quality-monitoring ecosystem on the production line.
