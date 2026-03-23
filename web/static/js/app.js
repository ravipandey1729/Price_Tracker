/**
 * Price Tracker Dashboard - Frontend JavaScript
 * Handles API interactions, charts, and UI updates
 */

// Global state
const app = {
    baseUrl: window.location.origin,
    apiUrl: window.location.origin + '/api',
    isLoading: false,
    notificationStream: null
};

// Utility Functions
function showLoading(element) {
    if (element) {
        element.disabled = true;
        const originalHTML = element.innerHTML;
        element.setAttribute('data-original-html', originalHTML);
        element.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Loading...';
    }
    app.isLoading = true;
}

function hideLoading(element) {
    if (element) {
        element.disabled = false;
        const originalHTML = element.getAttribute('data-original-html');
        if (originalHTML) {
            element.innerHTML = originalHTML;
        }
    }
    app.isLoading = false;
}

function showNotification(message, type = 'info') {
    // Create toast notification
    const toastHTML = `
        <div class="toast align-items-center text-white bg-${type === 'error' ? 'danger' : type} border-0" role="alert">
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;
    
    // Add to page (create container if doesn't exist)
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container position-fixed top-0 end-0 p-3';
        document.body.appendChild(container);
    }
    
    container.insertAdjacentHTML('beforeend', toastHTML);
    const toastElement = container.lastElementChild;
    const toast = new bootstrap.Toast(toastElement);
    toast.show();
    
    // Remove from DOM after hiding
    toastElement.addEventListener('hidden.bs.toast', () => {
        toastElement.remove();
    });
}

// API Functions
async function apiRequest(endpoint, options = {}) {
    const url = `${app.apiUrl}${endpoint}`;
    const token = localStorage.getItem('access_token');
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json'
        }
    };
    
    if (token) {
        defaultOptions.headers.Authorization = `Bearer ${token}`;
    }
    
    try {
        const response = await fetch(url, { ...defaultOptions, ...options });
        
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
            throw new Error(error.detail || `HTTP ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

function updateNotificationBadge(count) {
    const badge = document.getElementById('notifications-badge');
    if (!badge) return;

    if (count > 0) {
        badge.textContent = count > 99 ? '99+' : String(count);
        badge.classList.remove('d-none');
    } else {
        badge.classList.add('d-none');
    }
}

async function fetchUnreadCount() {
    if (!localStorage.getItem('access_token')) {
        updateNotificationBadge(0);
        return;
    }

    try {
        const result = await apiRequest('/notifications/unread-count');
        updateNotificationBadge(result.unread || 0);
    } catch (error) {
        console.error('Unread count failed:', error);
    }
}

function startNotificationStream() {
    const token = localStorage.getItem('access_token');
    if (!token) {
        if (app.notificationStream) {
            app.notificationStream.close();
        }
        return;
    }

    try {
        if (app.notificationStream) {
            app.notificationStream.close();
        }

        const streamUrl = `${app.apiUrl}/notifications/stream?token=${encodeURIComponent(token)}`;

        app.notificationStream = new EventSource(streamUrl);

        app.notificationStream.addEventListener('unread_count', (event) => {
            const unread = parseInt(event.data, 10) || 0;
            updateNotificationBadge(unread);
            if (unread > 0) {
                showNotification(`You have ${unread} unread notification(s)`, 'info');
            }
        });

        app.notificationStream.onerror = () => {
            // Keep the UX resilient with fallback polling
            if (app.notificationStream) {
                app.notificationStream.close();
            }
        };
    } catch (error) {
        console.error('Notification stream failed:', error);
    }
}

async function refreshAuthUi() {
    const authLink = document.getElementById('auth-link');
    const userLabelItem = document.getElementById('user-label-item');
    const userLabel = document.getElementById('user-label');
    const logoutItem = document.getElementById('logout-item');

    const token = localStorage.getItem('access_token');
    if (!token) {
        if (authLink) authLink.classList.remove('d-none');
        if (userLabelItem) userLabelItem.classList.add('d-none');
        if (logoutItem) logoutItem.classList.add('d-none');
        if (app.notificationStream) {
            app.notificationStream.close();
            app.notificationStream = null;
        }
        updateNotificationBadge(0);
        return;
    }

    try {
        const me = await apiRequest('/auth/me');
        if (authLink) authLink.classList.add('d-none');
        if (userLabelItem) userLabelItem.classList.remove('d-none');
        if (logoutItem) logoutItem.classList.remove('d-none');
        if (userLabel) userLabel.textContent = me.full_name || me.email;
        fetchUnreadCount();
        startNotificationStream();
    } catch (error) {
        localStorage.removeItem('access_token');
        if (authLink) authLink.classList.remove('d-none');
        if (userLabelItem) userLabelItem.classList.add('d-none');
        if (logoutItem) logoutItem.classList.add('d-none');
        if (app.notificationStream) {
            app.notificationStream.close();
            app.notificationStream = null;
        }
        updateNotificationBadge(0);
    }
}

// Health Check
async function checkSystemHealth() {
    try {
        const health = await apiRequest('/system/health');
        updateStatusIndicator(health.status === 'healthy');
        return health;
    } catch (error) {
        updateStatusIndicator(false);
        console.error('Health check failed:', error);
    }
}

function updateStatusIndicator(isHealthy) {
    const indicator = document.getElementById('status-indicator');
    const statusText = document.getElementById('status-text');
    
    if (indicator && statusText) {
        if (isHealthy) {
            indicator.className = 'bi bi-circle-fill text-success';
            statusText.textContent = 'Online';
        } else {
            indicator.className = 'bi bi-circle-fill text-danger';
            statusText.textContent = 'Offline';
        }
    }
}

// Format Functions
function formatCurrency(amount, currency = 'USD') {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: currency
    }).format(amount);
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    }).format(date);
}

function formatPercentage(value) {
    return `${value.toFixed(1)}%`;
}

// Chart Helper (for Chart.js)
function createLineChart(canvas, data, options = {}) {
    const defaultOptions = {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
            legend: {
                display: options.showLegend !== false
            },
            tooltip: {
                mode: 'index',
                intersect: false
            }
        },
        scales: {
            x: {
                display: true,
                grid: {
                    display: false
                }
            },
            y: {
                display: true,
                beginAtZero: false
            }
        }
    };
    
    return new Chart(canvas, {
        type: 'line',
        data: data,
        options: { ...defaultOptions, ...options }
    });
}

// Auto-refresh functionality
function enableAutoRefresh(intervalSeconds = 30) {
    console.log(`Auto-refresh enabled: ${intervalSeconds}s`);
    
    return setInterval(() => {
        console.log('Auto-refreshing page...');
        location.reload();
    }, intervalSeconds * 1000);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('Price Tracker Dashboard initialized');
    
    // Check system health
    checkSystemHealth();
    refreshAuthUi();
    
    // Check health every 30 seconds
    setInterval(checkSystemHealth, 30000);
    setInterval(fetchUnreadCount, 30000);
    
    // Add animation to cards
    const cards = document.querySelectorAll('.card');
    cards.forEach((card, index) => {
        setTimeout(() => {
            card.classList.add('animate-slide-in');
        }, index * 50);
    });
    
    // Handle form submissions with loading states
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', (e) => {
            const submitBtn = form.querySelector('[type="submit"]');
            if (submitBtn) {
                showLoading(submitBtn);
            }
        });
    });

    const logoutLink = document.getElementById('logout-link');
    if (logoutLink) {
        logoutLink.addEventListener('click', (event) => {
            event.preventDefault();
            localStorage.removeItem('access_token');
            showNotification('Logged out', 'info');
            setTimeout(() => {
                window.location.href = '/dashboard';
            }, 300);
        });
    }
});

// Export for use in other scripts
window.PriceTracker = {
    apiRequest,
    showNotification,
    showLoading,
    hideLoading,
    formatCurrency,
    formatDate,
    formatPercentage,
    createLineChart,
    checkSystemHealth
};
