/**
 * Complaint Management System - Utility Functions
 * Shared JavaScript utilities used across the application
 */

// ========== API CALLS ==========
async function apiCall(url, method = 'GET', data = null) {
    // Send API request and return JSON response
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json'
        }
    };

    if (data) {
        options.body = JSON.stringify(data);
    }

    try {
        const response = await fetch(url, options);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        showNotification('Error: ' + error.message, 'error');
        throw error;
    }
}

// ========== NOTIFICATIONS ==========
function showNotification(message, type = 'info') {
    // Show a toast notification to user
    const notification = document.createElement('div');
    notification.className = `alert alert-${type}`;
    notification.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        z-index: 9999;
        animation: slideIn 0.3s ease;
    `;
    notification.textContent = message;
    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 4000);
}

// ========== CONFIRMATION DIALOG ==========
function confirmAction(message) {
    // Show confirmation dialog
    return confirm(message);
}

// ========== DATE FORMATTING ==========
function formatDate(dateString) {
    // Format date string to readable format
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

function formatDateShort(dateString) {
    // Format date string to short format
    const date = new Date(dateString);
    return date.toLocaleDateString();
}

function getTimeAgo(dateString) {
    // Get human-readable time ago format
    const date = new Date(dateString);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);

    const intervals = {
        'year': 31536000,
        'month': 2592000,
        'week': 604800,
        'day': 86400,
        'hour': 3600,
        'minute': 60
    };

    for (const [key, value] of Object.entries(intervals)) {
        const interval = Math.floor(seconds / value);
        if (interval >= 1) {
            return interval + ' ' + key + (interval > 1 ? 's' : '') + ' ago';
        }
    }
    return 'just now';
}

// ========== FORM VALIDATION ==========
function validateEmail(email) {
    // Validate email format
    const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return regex.test(email);
}

function validatePassword(password) {
    // Validate password strength
    return password && password.length >= 6;
}

function validateComplaintForm(title, description, category) {
    // Validate complaint form fields
    const errors = [];

    if (!title || title.trim().length === 0) {
        errors.push('Title is required');
    } else if (title.length > 200) {
        errors.push('Title must be less than 200 characters');
    }

    if (!description || description.trim().length === 0) {
        errors.push('Description is required');
    } else if (description.length > 5000) {
        errors.push('Description must be less than 5000 characters');
    }

    if (!category) {
        errors.push('Category is required');
    }

    return errors;
}

// ========== LOADING STATES ==========
function setLoading(buttonElement, isLoading) {
    // Set button loading state
    if (isLoading) {
        buttonElement.disabled = true;
        buttonElement.textContent = '⏳ Loading...';
    } else {
        buttonElement.disabled = false;
        buttonElement.textContent = buttonElement.dataset.originalText || 'Submit';
    }
}

// ========== MODAL OPERATIONS ==========
function openModal(modalElement) {
    // Open modal
    modalElement.classList.add('show');
}

function closeModal(modalElement) {
    // Close modal
    modalElement.classList.remove('show');
}

function closeAllModals() {
    // Close all open modals
    document.querySelectorAll('.modal.show').forEach(modal => {
        modal.classList.remove('show');
    });
}

// ========== TABLE OPERATIONS ==========
function sortTableByColumn(table, columnIndex, descending = false) {
    // Sort table by column
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));

    rows.sort((a, b) => {
        const aVal = a.children[columnIndex].textContent;
        const bVal = b.children[columnIndex].textContent;

        if (descending) {
            return bVal.localeCompare(aVal);
        } else {
            return aVal.localeCompare(bVal);
        }
    });

    rows.forEach(row => tbody.appendChild(row));
}

function filterTableRows(table, searchText, columnIndices = [0, 1]) {
    // Filter table rows based on search text
    const rows = table.querySelectorAll('tbody tr');
    const searchLower = searchText.toLowerCase();

    rows.forEach(row => {
        let found = false;
        columnIndices.forEach(colIndex => {
            const cellText = row.children[colIndex].textContent.toLowerCase();
            if (cellText.includes(searchLower)) {
                found = true;
            }
        });
        row.style.display = found ? '' : 'none';
    });
}

// ========== LOCAL STORAGE ==========
function setLocalData(key, value) {
    // Store data in localStorage
    try {
        localStorage.setItem(key, JSON.stringify(value));
    } catch (e) {
        console.warn('LocalStorage not available:', e);
    }
}

function getLocalData(key) {
    // Retrieve data from localStorage
    try {
        const item = localStorage.getItem(key);
        return item ? JSON.parse(item) : null;
    } catch (e) {
        console.warn('LocalStorage not available:', e);
        return null;
    }
}

function removeLocalData(key) {
    // Remove data from localStorage
    try {
        localStorage.removeItem(key);
    } catch (e) {
        console.warn('LocalStorage not available:', e);
    }
}

// ========== DOM UTILITIES ==========
function addClass(element, className) {
    // Add CSS class to element
    element.classList.add(className);
}

function removeClass(element, className) {
    // Remove CSS class from element
    element.classList.remove(className);
}

function toggleClass(element, className) {
    // Toggle CSS class on element
    element.classList.toggle(className);
}

function hide(element) {
    // Hide element
    element.style.display = 'none';
}

function show(element, displayType = 'block') {
    // Show element
    element.style.display = displayType;
}

// ========== INITIALIZATION ==========
function applyTheme(theme) {
    document.body.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);

    const toggle = document.querySelector('.theme-toggle');
    if (toggle) {
        toggle.textContent = theme === 'dark' ? '☀️ Light' : '🌙 Dark';
        toggle.setAttribute('aria-pressed', theme === 'dark' ? 'true' : 'false');
    }

    const themeCheckbox = document.getElementById('theme-checkbox');
    if (themeCheckbox) {
        themeCheckbox.checked = (theme === 'dark');
        const themeSwitch = themeCheckbox.closest('.theme-switch');
        if (themeSwitch) {
            themeSwitch.setAttribute('title', theme === 'dark' ? 'Switch to Light Theme' : 'Switch to Dark Theme');
        }
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const savedTheme = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    applyTheme(savedTheme || (prefersDark ? 'dark' : 'light'));

    const navToggle = document.querySelector('.navbar-toggle');
    const navMenu = document.getElementById('main-nav-menu');
    const themeToggle = document.querySelector('.theme-toggle');
    const themeCheckbox = document.getElementById('theme-checkbox');

    if (themeCheckbox) {
        themeCheckbox.addEventListener('change', function() {
            applyTheme(this.checked ? 'dark' : 'light');
        });
    }

    if (themeToggle) {
        themeToggle.addEventListener('click', function(e) {
            if (e.target === themeCheckbox || e.target.closest('#theme-checkbox')) return;
            const currentTheme = document.body.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
            applyTheme(currentTheme);
        });
    }

    if (navToggle && navMenu) {
        navToggle.addEventListener('click', function() {
            const isOpen = navMenu.classList.toggle('is-open');
            navToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        });

        navMenu.querySelectorAll('.nav-link').forEach(function(link) {
            link.addEventListener('click', function() {
                navMenu.classList.remove('is-open');
                navToggle.setAttribute('aria-expanded', 'false');
            });
        });
    }

    // Close modals when clicking outside
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('modal')) {
            closeModal(e.target);
        }
    });

    // Close modals with Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeAllModals();
        }
    });

    // Add animations CSS if not present
    if (!document.querySelector('style[data-utils-css]')) {
        const style = document.createElement('style');
        style.setAttribute('data-utils-css', 'true');
        style.textContent = `
            @keyframes slideIn {
                from { transform: translateX(400px); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes slideOut {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(400px); opacity: 0; }
            }
        `;
        document.head.appendChild(style);
    }
});

// ========== EXPORT FOR DEBUGGING ==========
console.log('Campus Voice Utils Loaded');
