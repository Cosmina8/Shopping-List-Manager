# Shopping List Manager

A Flask-based web application for managing shopping lists with user authentication, item categorization, and CSV export functionality.

## Features

- **User Authentication**: Register and login with secure password hashing
- **Shopping Lists**: Create multiple shopping lists
- **Item Management**: 
  - Add items with quantity, unit, and category
  - Mark items as purchased
  - Delete items
  - Filter by category or pending items only
- **Data Export**: Export shopping lists to CSV format

## Requirements

- Python 3.7+
- See `requirements.txt` for dependencies

## Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the application:
   ```bash
   python app.py
   ```

3. Access the application at `http://localhost:5000`

## Project Structure

```
Shopping-List-Manager/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── static/
│   └── style.css         # CSS stylesheets
├── templates/
│   ├── _base.html        # Base template
│   ├── index.html        # Home page
│   ├── login.html        # Login page
│   ├── register.html     # Registration page
│   ├── dashboard.html    # User dashboard
│   └── list.html         # Shopping list view
└── tests/
    └── test_app.py       # Unit tests
```

## Database

The application uses SQLite with the following tables:
- **users**: User accounts with username and password hash
- **lists**: Shopping lists associated with users
- **items**: Individual items in shopping lists with quantity, unit, and category info

## Usage

1. Register a new account
2. Create shopping lists from the dashboard
3. Add items to your lists with optional quantity, unit, and category
4. Mark items as purchased when shopping
5. Export lists to CSV for offline use
