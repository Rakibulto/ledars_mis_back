# Ledar's Backend HRM - Project Documentation

## 1. Project Overview

This document provides a detailed overview of the Ledar's Backend HRM, a comprehensive Human Resource Management (HRM) system built with Django and Django REST Framework. The system is designed to manage employees, attendance, leave, shifts, holidays, and notifications, providing a robust backend for HR operations.

### 1.1. Technology Stack

-   **Backend Framework:** Django
-   **API:** Django REST Framework (DRF)
-   **Authentication:** Djoser with JSON Web Tokens (JWT)
-   **Database:** PostgreSQL (recommended), SQLite (development)

### 1.2. Core Modules

The project is structured into the following Django apps (modules):

-   **Authentication:** Manages user accounts, roles, permissions, and JWT-based authentication.
-   **Employee:** Handles all employee-related information, including personal and official details, as well as organizational structure (departments, designations, branches).
-   **Attendance:** Tracks employee attendance, processes check-in/out data, and manages adjustment requests.
-   **Shift:** Defines employee work schedules and shift timings.
-   **Holiday:** Manages company holidays, with support for global and targeted rules.
-   **Leave:** Manages leave policies, leave requests, and the approval workflow.
-   **Notification:** Provides a system for real-time notifications for various HR events.

---

## 2. Authentication Module (`authentication`)

### 2.1. Purpose

The `authentication` module is responsible for user management, role-based access control (RBAC), and securing API endpoints. It extends Django's default user model and integrates `Djoser` for handling registration, login, and other authentication-related tasks.

### 2.2. Features

-   **Custom User Model:** A custom `User` model that uses email as the primary identifier.
-   **Role-Based Access Control:** `Role` model (e.g., Admin, Supervisor, Employee) to assign permissions.
-   **IP Whitelisting:** `PreApprovedIP` model to restrict web login access to specific IP addresses.
-   **JWT Authentication:** Uses `djoser` and `rest_framework_simplejwt` for secure token-based authentication.
-   **Account Activation:** Email-based account activation workflow.

### 2.3. API Endpoints

All authentication endpoints are prefixed with `/api/`.

| Method | URL                                               | Description                                       |
| :----- | :------------------------------------------------ | :------------------------------------------------ |
| **POST** | `/auth/users/`                                    | Register a new user.                              |
| **GET**  | `/auth/users/`                                    | List all users (Admin only).                      |
| **GET**  | `/auth/users/me/`                                 | Get details of the authenticated user.            |
| **POST** | `/auth/jwt/create/`                               | Obtain a JWT token pair (login).                  |
| **POST** | `/auth/jwt/refresh/`                              | Refresh an expired JWT access token.              |
| **POST** | `/auth/jwt/verify/`                               | Verify a JWT token.                               |
| **GET**  | `/activate/<uid>/<token>/`                        | Activate a user account via an email link.        |
| **PUT**  | `/update-user/<pk>/`                              | Update user details.                              |
| **GET**  | `/permissions/`                                   | List all available permissions in the system.     |
| **POST** | `/set-user-permissions/<user_id>/`                | Set specific permissions for a user.              |
| **GET/POST** | `/user-roles/`                                | List or create user roles.                        |
| **GET/PUT/DELETE** | `/user-roles/<pk>/`                     | Retrieve, update, or delete a user role.          |
| **GET/POST** | `/pre-approved-ip-list/`                      | List or create pre-approved IP addresses.         |
| **PUT/DELETE** | `/pre-approved-ip-update-and-delete/<pk>/`  | Update or delete a pre-approved IP address.       |

---

## 3. Employee Module (`employee`)

### 3.1. Purpose

This module is the central hub for all employee information. It manages detailed profiles, organizational structure, and relationships between employees (like supervisors).

### 3.2. Features

-   **Comprehensive Employee Model:** The `Employee` model stores everything from personal details (DOB, address) to official information (joining date, salary, department).
-   **Organizational Structure:** `Department`, `Designation`, and `Branch` models define the company's structure.
-   **Emergency & Nominee Contacts:** Manages employee emergency contacts and nominee information.
-   **Supervisor Management:** Links employees to their supervisors.
-   **Status Tracking:** Employee status can be `active`, `resigned`, `terminated`, or `incomplete`.

### 3.3. API Endpoints

All employee endpoints are prefixed with `/api/`.

| Method | URL                               | Description                                       |
| :----- | :-------------------------------- | :------------------------------------------------ |
| **GET/POST** | `/employees/`                     | List all employees or create a new one.           |
| **GET/PUT/DELETE** | `/employees/<user__pk>/`      | Retrieve, update, or delete an employee by user ID. |
| **GET/POST** | `/departments/`                   | List all departments or create a new one.         |
| **GET/PUT/DELETE** | `/departments/<pk>/`            | Retrieve, update, or delete a department.         |
| **GET/POST** | `/designations/`                  | List all designations or create a new one.        |
| **GET/PUT/DELETE** | `/designations/<pk>/`           | Retrieve, update, or delete a designation.        |
| **GET/POST** | `/branches/`                      | List all branches or create a new one.            |
| **GET/PUT/DELETE** | `/branches/<pk>/`               | Retrieve, update, or delete a branch.             |
| **GET**  | `/supervisors/`                   | List all users with the 'Supervisor' role.        |

---

## 4. Shift Module (`shift`)

### 4.1. Purpose

Defines the various work shifts for employees, which is critical for the `attendance` module to calculate lateness, overtime, etc.

### 4.2. Features

-   **Flexible Shift Timings:** The `Shift` model defines `office_start_time`, `office_end_time`, and check-in/check-out windows.
-   **Grace Periods:** Includes consideration times for late arrivals and early departures.

### 4.3. API Endpoints

All shift endpoints are prefixed with `/api/`.

| Method | URL                   | Description                               |
| :----- | :-------------------- | :---------------------------------------- |
| **GET**  | `/shifts/`            | List all available shifts.                |
| **POST** | `/shifts/create`      | Create a new shift.                       |
| **PUT/DELETE** | `/shifts/<id>/`   | Update or delete a specific shift.        |

---

## 5. Holiday Module (`holiday`)

### 5.1. Purpose

Manages company holidays and determines their applicability to different groups of employees.

### 5.2. Features

-   **Date Ranges:** Supports single-day and multi-day holidays.
-   **Flexible Assignment:** Holidays can be global or assigned to specific branches, departments, designations, or employment types.
-   **Exclusions:** Allows specific employees to be excluded from a holiday.

### 5.3. API Endpoints

All holiday endpoints are prefixed with `/api/`.

| Method | URL             | Description                               |
| :----- | :-------------- | :---------------------------------------- |
| **GET/POST** | `/holidays/`    | List all holidays or create a new one.    |
| **GET/PUT/DELETE** | `/holidays/<pk>/` | Retrieve, update, or delete a holiday.    |

---

## 6. Leave Module (`leave`)

### 6.1. Purpose

Handles all aspects of employee leave, from defining policies to managing requests and approvals.

### 6.2. Features

-   **Leave Policies:** `LeavePolicy` model defines rules for different leave types (e.g., total days, gender restrictions, application deadlines).
-   **Leave Groups:** `LeaveGroup` model categorizes employees to apply specific sets of policies.
-   **Multi-Level Approvals:** `SupervisorLevel` and `LeaveApproval` models create a hierarchical approval workflow.
-   **Leave Balance Calculation:** A `LeaveBalanceCalculator` utility computes available leave days, considering holidays, weekends, and policy rules.
-   **Compensatory Leave:** Manages earned and used compensatory time off.

### 6.3. API Endpoints

All leave endpoints are prefixed with `/api/`.

| Method | URL                                                 | Description                                                              |
| :----- | :-------------------------------------------------- | :----------------------------------------------------------------------- |
| **GET/POST** | `/leave-groups/`                                | List or create leave groups.                                             |
| **GET/POST** | `/leave-policies/`                              | List or create leave policies.                                           |
| **GET**  | `/employees/<employee_id>/leave-policies/`        | List the leave policies applicable to a specific employee.               |
| **GET/POST** | `/leave-requests/`                              | List all leave requests or create a new one.                             |
| **GET/PUT/DELETE** | `/leave-requests/<pk>/`                   | Retrieve, update, or delete a leave request.                             |
| **GET/POST** | `/supervisor-level-list-create/`                | List or create supervisor approval levels for employees.                 |
| **GET**  | `/leave-approval/`                                | List leave approvals. Can be filtered by approver or request.             |
| **PUT**  | `/leave-approval/<pk>/`                           | Update (approve/reject) a leave approval.                                |
| **GET**  | `/leave-balance/<employee_id>/`                   | Get the leave balance for a specific employee.                           |
| **GET/POST** | `/compensatory-leave/`                          | View or add compensatory leave records.                                  |

---

## 7. Attendance Module (`attendance`)

### 7.1. Purpose

This is a highly complex module responsible for tracking employee attendance, calculating work hours, and managing adjustments.

### 7.2. Features

-   **Real-time Data Capture:** The `AttendanceData` model stores raw check-in/out timestamps from devices or web logins.
-   **Automated Status Calculation:** Automatically determines attendance status (Present, Late, Absent, etc.) based on the employee's shift.
-   **Historical Records:** `AttendanceHistory` model stores a processed summary of daily attendance.
-   **Adjustment Workflow:** `AttendanceAdjustmentRequest` allows employees to request corrections, which go through an approval process.
-   **Reporting:** Provides comprehensive attendance reports with various filters.
-   **Cut-Off Periods:** `CutOff` model defines periods for payroll and report generation.

### 7.3. API Endpoints

All attendance endpoints are prefixed with `/api/`.

| Method | URL                                                 | Description                                                              |
| :----- | :-------------------------------------------------- | :----------------------------------------------------------------------- |
| **GET**  | `/attendance-report/`                             | Get a comprehensive attendance report for multiple employees.            |
| **GET**  | `/attendance-report/<pk>/`                        | Get a detailed attendance report for a single employee.                  |
| **POST** | `/attendance-create/`                             | Create a new attendance record (check-in/out).                           |
| **GET**  | `/attendance/<employee_id>/`                      | Get all attendance records for a specific employee.                      |
| **POST** | `/attendance-adjustment-create/`                  | Create a new attendance adjustment request.                              |
| **GET**  | `/attendance_approval_list/`                      | List attendance adjustment approvals.                                    |
| **PUT**  | `/attendance_approval_update/<pk>/`               | Update (approve/reject) an attendance adjustment.                        |
| **GET**  | `/dashboard/`                                     | Get a high-level HR dashboard with attendance analytics.                 |

---

## 8. Notification Module (`notification`)

### 8.1. Purpose

Provides a simple, real-time notification system for important events within the HRM application.

### 8.2. Features

-   **Typed Notifications:** Notifications are categorized by type (e.g., `leave`, `attendance`).
-   **Read/Unread Status:** Tracks whether a notification has been viewed.
-   **Sender/Receiver:** Links notifications to the user who triggered the event and the user who should receive it.

### 8.3. API Endpoints

All notification endpoints are prefixed with `/api/`.

| Method | URL                   | Description                                                      |
| :----- | :-------------------- | :--------------------------------------------------------------- |
| **GET**  | `/notifications/`     | List notifications. Can be filtered by receiver, employee, or type. |
| **GET/PUT/DELETE** | `/notifications/<pk>/` | Retrieve, update (e.g., mark as read), or delete a notification. |
