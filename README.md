# Shopping List Manager

A Flask-based web application for managing shopping lists with user authentication, item categorization, and CSV export functionality.

## Features

- **User Authentication**: Register and login with secure password hashing
- **Shopping Lists**: Create, edit, and delete multiple shopping lists
- **Item Management**: 
  - Add items with quantity, unit, category, and price
  - Mark items as purchased
  - Edit and delete items
  - Filter by category or pending items only
  - Handle duplicate items (update/combine/add new)
- **Data Export**: Export shopping lists to CSV format

---

## Technologies

- **Backend**: Python (Flask)
- **Database**: Firebase Firestore (NoSQL)
- **Frontend**: HTML, CSS (Jinja templates)

---

## Requirements

- Python 3.7+
- See `requirements.txt` for dependencies

---

## Installation

1. Clone the repository:

```bash
git clone <your-repo-url>
cd Shopping-List-Manager
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Add Firebase credentials:

Download your Firebase service account JSON and place it in the project root as:

```
firebase_service_account.json
```

⚠️ This file is NOT included in the repository for security reasons.

4. Run the application:

```bash
python app.py
```

5. Access the application at:

```
http://localhost:5000
```

---

## Project Structure

```
Shopping-List-Manager/
├── app.py                     # Main Flask application
├── firebase_config.py         # Firebase connection setup
├── requirements.txt           # Python dependencies
├── README.md                  # Project documentation
├── static/
│   └── style.css              # CSS styles
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   ├── list.html
│   ├── edit_item.html
│   ├── edit_list.html
│   └── add_confirm.html
└── tests/
    └── test_app.py
```

---

## Database

The application uses **Firebase Firestore (NoSQL)** with the following collections:

### users
- username  
- password_hash  
- created_at  

### lists
- user_id  
- name  
- created_at  

### items
- list_id  
- name  
- qty  
- unit  
- category  
- price  
- purchased  
- created_at  

---

## Usage

1. Register a new account  
2. Log in  
3. Create shopping lists  
4. Add items with optional details (quantity, unit, category, price)  
5. Manage items (edit, delete, mark as purchased)  
6. Export lists to CSV  

---

## Notes

- The application was originally built using SQLite and later migrated to Firebase Firestore.
- Firestore uses document-based storage, so IDs are strings instead of integers.
- The Firebase service account file is required to run the project locally.

---

## Security

- Passwords are securely hashed using Werkzeug
- Firebase credentials are excluded via `.gitignore`