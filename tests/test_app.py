import unittest
import os
import sys
import uuid

# Add parent directory to path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from firebase_config import db
from werkzeug.security import generate_password_hash


class ShoppingListManagerTestCase(unittest.TestCase):
    """Test cases for Shopping List Manager application (Firestore version)"""

    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

        self.created_user_ids = []
        self.created_list_ids = []

    def tearDown(self):
        """Clean up created Firestore documents after each test"""
        for list_id in self.created_list_ids:
            try:
                # delete items from this list first
                items = db.collection("items").where("list_id", "==", list_id).stream()
                for item in items:
                    db.collection("items").document(item.id).delete()

                db.collection("lists").document(list_id).delete()
            except Exception:
                pass

        for user_id in self.created_user_ids:
            try:
                # delete lists for this user
                lists = db.collection("lists").where("user_id", "==", user_id).stream()
                for lst in lists:
                    # delete items from each list
                    items = db.collection("items").where("list_id", "==", lst.id).stream()
                    for item in items:
                        db.collection("items").document(item.id).delete()

                    db.collection("lists").document(lst.id).delete()

                db.collection("users").document(user_id).delete()
            except Exception:
                pass

    def create_test_user(self, username=None, password='testpass123'):
        """Create a user directly in Firestore for testing"""
        if username is None:
            username = f"testuser_{uuid.uuid4().hex[:8]}"

        password_hash = generate_password_hash(password)
        user_ref = db.collection("users").document()
        user_ref.set({
            "username": username,
            "password_hash": password_hash,
            "created_at": "2026-04-20T12:00:00"
        })

        self.created_user_ids.append(user_ref.id)
        return {
            "id": user_ref.id,
            "username": username,
            "password": password
        }

    def create_test_list(self, user_id, name="Test List"):
        """Create a shopping list directly in Firestore for testing"""
        list_ref = db.collection("lists").document()
        list_ref.set({
            "user_id": user_id,
            "name": name,
            "created_at": "2026-04-20T12:05:00"
        })

        self.created_list_ids.append(list_ref.id)
        return {
            "id": list_ref.id,
            "name": name
        }

    def test_index_redirects_when_logged_in(self):
        """Test that logged-in users are redirected from index to dashboard"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = "test_user_id"

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
        username = f"reguser_{uuid.uuid4().hex[:8]}"

        response = self.client.post('/register', data={
            'username': username,
            'password': 'testpass123'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'login', response.data.lower())

        # verify user exists in Firestore
        docs = db.collection("users").where("username", "==", username).limit(1).stream()
        found_user = None
        for doc in docs:
            found_user = doc
            self.created_user_ids.append(doc.id)
            break

        self.assertIsNotNone(found_user)

    def test_register_post_missing_credentials(self):
        """Test registration with missing username or password"""
        response = self.client.post('/register', data={
            'username': '',
            'password': 'testpass123'
        }, follow_redirects=True)

        self.assertIn(b'username', response.data.lower())

    def test_login_get(self):
        """Test GET request to login page"""
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)

    def test_login_success(self):
        """Test successful login"""
        user = self.create_test_user(password='testpass123')

        response = self.client.post('/login', data={
            'username': user['username'],
            'password': 'testpass123'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'dashboard', response.data.lower())

    def test_login_wrong_password(self):
        """Test login with wrong password"""
        user = self.create_test_user(password='correctpass')

        response = self.client.post('/login', data={
            'username': user['username'],
            'password': 'wrongpass'
        }, follow_redirects=True)

        self.assertIn(b'username', response.data.lower())

    def test_logout(self):
        """Test logout clears session"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = "test_user_id"

        self.client.get('/logout', follow_redirects=True)

        with self.client.session_transaction() as sess:
            self.assertNotIn('user_id', sess)

    def test_dashboard_requires_login(self):
        """Test that dashboard is protected by login_required decorator"""
        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.location)

    def test_dashboard_shows_lists(self):
        """Test dashboard displays user's shopping lists"""
        user = self.create_test_user()
        self.create_test_list(user["id"], "Test List")

        with self.client.session_transaction() as sess:
            sess['user_id'] = user["id"]
            sess['username'] = user["username"]

        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Test List', response.data)

    def test_create_list(self):
        """Test creating a new shopping list"""
        user = self.create_test_user()

        with self.client.session_transaction() as sess:
            sess['user_id'] = user["id"]
            sess['username'] = user["username"]

        response = self.client.post('/lists/create', data={'name': 'My List'}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        # verify list was created in Firestore
        docs = db.collection("lists").where("user_id", "==", user["id"]).where("name", "==", "My List").stream()
        found_list = None
        for doc in docs:
            found_list = doc
            self.created_list_ids.append(doc.id)
            break

        self.assertIsNotNone(found_list)


if __name__ == '__main__':
    unittest.main()