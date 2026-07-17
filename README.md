# Ledar's Backend HRM

A comprehensive Human Resource Management (HRM) system backend built with Django, designed to streamline HR operations for organizations. This system provides robust functionality for managing employees, attendance, leave requests, shifts, holidays, and notifications.

## 🚀 Features

### Core Modules

#### 👥 Employee Management

- Comprehensive employee profile management
- Personal details (address, marital status, blood group, gender, contact information)
- Official information (employee ID, department, designation, branch, joining date, salary)
- Employment type tracking and supervisor assignment
- Master data management for departments, designations, and branches

#### ⏰ Attendance Management

- Real-time attendance tracking with check-in/check-out functionality
- Automatic attendance status calculation (Present, Late, Absent, Overtime, Early Leave, Half Day, Holiday, Weekend)
- Integration with employee shift schedules and company holidays
- Attendance adjustment request processing
- Comprehensive attendance reporting

#### 🏖️ Leave Management

- Flexible leave policy configuration with multiple leave types
- Gender-specific leave policies and advance application requirements
- Multi-level approval workflow with supervisor integration
- Leave balance tracking and automatic calculations
- Half-day leave support and leave transfer capabilities
- Employee categorization into leave groups

#### 🔐 Authentication & Authorization

- Custom user model with role-based access control
- Granular permission system (Admin, Supervisor roles)
- IP address pre-approval for enhanced web login security
- User account activation and management
- Secure authentication workflows

#### 📅 Holiday Management

- Global holiday configuration for all employees
- Targeted holiday assignment by branch, department, designation, or employment type
- Individual employee holiday customization
- Holiday exclusion management for specific employees

#### 🔔 Notification System

- Real-time notifications for HR events
- Leave request status updates
- Attendance adjustment notifications
- Probation period alerts
- Read/unread notification tracking

#### ⏱️ Shift Management

- Flexible shift configuration and timing management
- Official office hours definition
- Check-in/check-out window configuration
- Late arrival and early departure consideration periods
- Multiple shift support for different employee groups

## 🛠️ Technology Stack

- **Backend Framework:** Django
- **Database:** PostgreSQL/SQLite (configurable)
- **Authentication:** Djoser (JWT)
- **API:** Django REST Framework
- **Environment:** Python 3.8+

## 📋 Prerequisites

- Python 3.8 or higher
- pip (Python package installer)
- Virtual environment (recommended)
- Database system (PostgreSQL recommended for production)

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/Raktch/Jago-Ledar's-Backend-HRM.git
cd Jago-Ledar's-Backend-HRM
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Environment Variable (Optional)

By default, the project runs in **development** mode. To switch to **production**:

- **Linux/macOS:**

  ```bash
  export DJANGO_ENVIRONMENT=production
  ```

- **Windows CMD:**

  ```cmd
  set DJANGO_ENVIRONMENT=production
  ```

- **Windows PowerShell:**

  ```powershell
  $env:DJANGO_ENVIRONMENT = "production"
  ```

### 5. Database Setup

```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Create Superuser

```bash
python manage.py createsuperuser
```

### 7. Seed Database with Sample Data (Optional)

#### `seed_role`

Seeds predefined **Roles** used to categorize employees.

```bash
python manage.py seed_role
```

#### `seed_shifts`

Seeds predefined **Shifts** used to categorize employees.

```bash
python manage.py seed_shifts
```

#### `leave_groups`

Seeds predefined **Leave Groups** used to categorize employees.

```bash
python manage.py leave_groups
```

#### `leave_policies`

Seeds predefined **Leave Groups** used to categorize employees.

```bash
python manage.py leave_policies

```

**Creates the following groups (if not already present):**

- General Staff (Probation)
- General Staff (Regular)
- Teachers (Probation)
- Teachers (Regular)

---

#### `seed_leave_policies`

Seeds unique **Leave Policies** for each leave group. Skips policies if they already exist for a given group.

```bash
python manage.py seed_leave_policies
```

---

#### `special_leave_policies`

Seeds unique **Special Leave Policies** for each leave policies.

```bash
python manage.py special_leave_policies
```

#### `Set Employee Permissions`

Seed permissions for Employee Role Users.

```bash
python manage.py seed_employee_permissions
```

### Seed All Data Together

```bash
python manage.py seed_all_data
```

**Group-wise policies:**

#### General Staff (Probation & Regular)

- Medical Leave — 0 days apply-before
- Casual Leave — 1 day apply-before
- Maternity Leave — 30 days apply-before
- Paternity Leave — 7 days apply-before
- Annual Leave — 10 days apply-before
- Compensatory Leave — 0 days apply-before (validity: 30 days)
- Duty Leave / On-Duty — 1 day apply-before
- Bereavement Leave — 0 days apply-before
- Emergency Leave — 0 days apply-before

#### Teachers (Probation & Regular)

- Medical Leave — 0 days apply-before
- Casual Leave — 1 day apply-before
- Maternity Leave — 30 days apply-before
- Paternity Leave — 7 days apply-before
- Bereavement Leave — 0 days apply-before
- Duty Leave / On-Duty — 1 day apply-before
- Study Leave — 1 day apply-before

### 📎 Notes

- Re-running the seeders is safe: they skip duplicates.
- Customize policy durations, group names, or supervisor levels via frontend/models/admin.

### 8. Run Development Server

```bash
python manage.py runserver
```

The application will be available at `http://localhost:8000`

## 📁 Project Structure

```
Jago-Ledar's-Backend-HRM/
├── attendance/          # Attendance management app
│   └── management/
│       └── commands/
│           └── seed_attendance.py  # Attendance & employee seeder
├── authentication/      # User authentication and authorization
├── employee/           # Employee information management
├── holiday/            # Holiday management system
├── leave/              # Leave management and policies
│   └── management/
│       └── commands/
            └── leave_groups.py        # Leave group seeder
│           └── leave_policies.py      # Leave policy seeder
├── notification/       # Notification system
├── shift/              # Shift management
├── static/             # Static files
├── media/              # Media uploads
├── templates/          # HTML templates
├── requirements.txt    # Python dependencies
├── manage.py          # Django management script
└── README.md          # Project documentation
```

## 🔧 Configuration

### .env Configuration Example

Create a `.env` file in your project root with the following content:

```
# For local development
# DOMAIN = '127.0.0.1:8000'
# SITE_NAME = 'Ledar's'
# FRONTEND_URL='http://localhost:3000'

# For production
DOMAIN = 'Ledar'sapi.raktch.com'
SITE_NAME = 'Ledar's'
FRONTEND_URL='https://Ledar's.raktch.com'

# Email settings
EMAIL_HOST_USER = 'your-email@example.com'
EMAIL_HOST_PASSWORD = 'your-email-password'
```

## 🔐 Security Features

- **IP Whitelisting:** Pre-approved IP addresses for web login access
- **Role-based Access Control:** Granular permissions for different user roles
- **Secure Authentication:** Django's robust authentication system with custom extensions
- **Data Validation:** Comprehensive input validation and sanitization

## 📊 Key Workflows

### Leave Request Process

1. Employee submits leave request
2. System validates against leave policies and balances
3. Notification sent to supervisor
4. Supervisor reviews and approves/rejects
5. Employee and HR receive status notifications
6. Leave balance automatically updated upon approval

### Attendance Tracking

1. Employee checks in/out through the system
2. System calculates attendance status based on shift timings
3. Late arrivals, early departures, and overtime automatically detected
4. Integration with holiday calendar for accurate status determination
5. Attendance adjustment requests processed through approval workflow

## 🐛 Troubleshooting

### Common Issues

**Database Connection Error:**

- Verify database credentials in settings
- Ensure database server is running
- Check network connectivity

**Migration Issues:**

```bash
python manage.py makemigrations --empty appname
python manage.py migrate --fake-initial
```

**Static Files Not Loading:**

```bash
python manage.py collectstatic
```

---

**Version:** 1.0.0

**Last Updated:** July 2025
**Maintained by:** Raktch Technology & Software
