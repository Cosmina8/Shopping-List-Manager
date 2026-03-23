import unittest
import os
import sys
import tempfile
from datetime import datetime

# Add parent directory to path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, init_db, get_db, DB_PATH
from werkzeug.security import generate_password_hash


class ShoppingListManagerTestCase(unittest.TestCase):
    """Test cases for Shopping List Manager application"""

    def setUp(self):
        """Set up test client and database before each test"""
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        
        # Use temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db_path = self.temp_db.name
        self.temp_db.close()
        
        # Patch DB_PATH for tests
        global DB_PATH
        self.original_db_path = DB_PATH
        app.config['DB_PATH'] = self.temp_db_path

    def tearDown(self):
        """Clean up after each test"""
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)

    def test_index_redirects_when_logged_in(self):
        """Test that logged-in users are redirected from index to dashboard"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
        
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('dashboard', response.location)

    def test_index_shows_page_when_not_logged_in(self):
        """Test that index page is shown to non-logged-in users"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_register_get(self):
        """Test GET request to register page"""
        response = self.client.get('/register')
        self.assertEqual(response.status_code, 200)

    def test_register_post_success(self):
        """Test successful user registration"""
        response = self.client.post('/register', data={
            'username': 'testuser',
            'password': 'testpass123'
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        # Should redirect to login after successful registration
        self.assertIn(b'login', response.data.lower() or response.location.lower())

    def test_register_post_missing_credentials(self):
        """Test registration with missing username or password"""
        response = self.client.post('/register', data={
            'username': '',
            'password': 'testpass123'
        }, follow_redirects=True)
        
        # Should show error message
        self.assertIn(b'username', response.data.lower())

    def test_login_get(self):
        """Test GET request to login page"""
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)

    def test_login_success(self):
        """Test successful login"""
        # First create a user
        conn = get_db()
        cur = conn.cursor()
        password_hash = generate_password_hash('testpass123')
        cur.execute(
            "INSERT INTO users(username, password_hash, created_at) VALUES (?, ?, ?)",
            ('loginuser', password_hash, datetime.utcnow().isoformat())
        )
        conn.commit()
        conn.close()
        
        # Now login
        response = self.client.post('/login', data={
            'username': 'loginuser',
            'password': 'testpass123'
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'dashboard', response.data.lower() or response.location.lower())

    def test_login_wrong_password(self):
        """Test login with wrong password"""
        # First create a user
        conn = get_db()
        cur = conn.cursor()
        password_hash = generate_password_hash('correctpass')
        cur.execute(
            "INSERT INTO users(username, password_hash, created_at) VALUES (?, ?, ?)",
            ('testuser2', password_hash, datetime.utcnow().isoformat())
        )
        conn.commit()
        conn.close()
        
        # Try to login with wrong password
        response = self.client.post('/login', data={
            'username': 'testuser2',
            'password': 'wrongpass'
        }, follow_redirects=True)
        
        self.assertIn(b'username', response.data.lower())

    def test_logout(self):
        """Test logout clears session"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
        
        response = self.client.get('/logout', follow_redirects=True)
        
        # Session should be cleared after logout
        with self.client.session_transaction() as sess:
            self.assertNotIn('user_id', sess)

    def test_dashboard_requires_login(self):
        """Test that dashboard is protected by login_required decorator"""
        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.location)

    def test_dashboard_shows_lists(self):
        """Test dashboard displays user's shopping lists"""
        # Create a user
        conn = get_db()
        cur = conn.cursor()
        password_hash = generate_password_hash('testpass')
        cur.execute(
            "INSERT INTO users(username, password_hash, created_at) VALUES (?, ?, ?)",
            ('dashuser', password_hash, datetime.utcnow().isoformat())
        )
        conn.commit()
        
        # Get user ID
        cur.execute("SELECT id FROM users WHERE username = 'dashuser'")
        user_id = cur.fetchone()[0]
        
        # Create a shopping list
        cur.execute(
            "INSERT INTO lists(user_id, name, created_at) VALUES (?, ?, ?)",
            (user_id, 'Test List', datetime.utcnow().isoformat())
        )
        conn.commit()
        conn.close()
        
        # Login and access dashboard
        with self.client.session_transaction() as sess:
            sess['user_id'] = user_id
        
        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Test List', response.data)

    def test_create_list(self):
        """Test creating a new shopping list"""
        # Create and login user
        conn = get_db()
        cur = conn.cursor()
        password_hash = generate_password_hash('testpass')
        cur.execute(
            "INSERT INTO users(username, password_hash, created_at) VALUES (?, ?, ?)",
            ('listuser', password_hash, datetime.utcnow().isoformat())
        )
        conn.commit()
        cur.execute("SELECT id FROM users WHERE username = 'listuser'")
        user_id = cur.fetchone()[0]
        conn.close()
        
        with self.client.session_transaction() as sess:
            sess['user_id'] = user_id
        
        # Create a list
        response = self.client.post('/lists/create', data={'name': 'My List'}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        
        # Verify list was created
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM lists WHERE name = 'My List'")
        lst = cur.fetchone()
        conn.close()
        
        self.assertIsNotNone(lst)
        self.assertEqual(lst['user_id'], user_id)


if __name__ == '__main__':
    unittest.main()
