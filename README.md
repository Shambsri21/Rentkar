# EV Rental System

A full-stack vehicle rental system built with Django, MySQL, and Bootstrap, focusing on promoting EV adoption through vehicle options.

## Features

- User authentication with Google OAuth
- Vehicle management (2-wheelers, 4-wheelers, EVs, petrol, diesel)
- Booking system with status tracking
- Manager dashboard for branch management
- Responsive design with Bootstrap 5

## Prerequisites

- Python 3.8+
- MySQL Server
- Google OAuth credentials

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd vehicle_rental
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a MySQL database:
```sql
CREATE DATABASE vehicle_rental;
```

5. Configure environment variables:
Create a `.env` file in the project root with the following variables:
```
SECRET_KEY=your-secret-key
DB_NAME=vehicle_rental
DB_USER=your-mysql-username
DB_PASSWORD=your-mysql-password
DB_HOST=localhost
DB_PORT=3306
```

6. Set up Google OAuth:
- Go to Google Cloud Console
- Create a new project
- Enable Google+ API
- Create OAuth 2.0 credentials
- Add authorized redirect URIs:
  - http://localhost:8000/accounts/google/login/callback/
  - http://127.0.0.1:8000/accounts/google/login/callback/

7. Run migrations:
```bash
python manage.py makemigrations
python manage.py migrate
```

8. Create a superuser:
```bash
python manage.py createsuperuser
```

9. Run the development server:
```bash
python manage.py runserver
```

## Usage

1. Access the admin interface at `http://localhost:8000/admin/`
2. Create a manager account through the admin interface
3. Add vehicles through the manager dashboard
4. Users can browse and book vehicles through the main interface

## Project Structure

```
vehicle_rental/
├── rental/                    # Main app
│   ├── migrations/            # Database migrations
│   ├── templates/             # HTML templates
│   ├── models.py              # Database models
│   ├── views.py               # View functions
│   ├── forms.py               # Form classes
│   └── urls.py                # URL patterns
├── vehicle_rental/            # Project settings
├── static/                    # Static files
├── media/                     # User uploaded files
└── requirements.txt           # Project dependencies
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 