document.addEventListener('DOMContentLoaded', () => {
    // Common utilities
    const getWeekStart = () => {
        const today = new Date();
        const day = today.getDay();
        const diff = today.getDate() - day + (day === 0 ? -6 : 1);
        return new Date(today.setDate(diff));
    };

    const formatDateRange = (startDate) => {
        const endDate = new Date(startDate);
        endDate.setDate(endDate.getDate() + 6);
        return `${startDate.toLocaleDateString()} - ${endDate.toLocaleDateString()}`;
    };

    // Navigation
    const navTabs = document.querySelectorAll('.nav-tab');
    const tabContents = document.querySelectorAll('.tab-content');

    navTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            navTabs.forEach(t => t.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById(`${tab.dataset.tab}Tab`).classList.add('active');
            
            if (tab.dataset.tab === 'dashboard') {
                updateDashboard();
            } else if (tab.dataset.tab === 'availability') {
                updateAvailabilityTab();
            } else if (tab.dataset.tab === 'performance') {
                updatePerformanceTab();
            } else if (tab.dataset.tab === 'ai-settings') {
                checkOllamaStatus();
            }
        });
    });

    // Notifications
    const notificationBtn = document.getElementById('notificationBtn');
    const notificationPanel = document.getElementById('notificationPanel');
    notificationBtn?.addEventListener('click', () => {
        notificationPanel.style.display = notificationPanel.style.display === 'block' ? 'none' : 'block';
    });

    // User Menu
    const userMenuBtn = document.getElementById('userMenuBtn');
    const userMenuPanel = document.getElementById('userMenuPanel');
    userMenuBtn?.addEventListener('click', () => {
        userMenuPanel.style.display = userMenuPanel.style.display === 'block' ? 'none' : 'block';
    });

    // Close panels when clicking outside
    document.addEventListener('click', (e) => {
        if (!notificationBtn.contains(e.target) && !notificationPanel.contains(e.target)) {
            notificationPanel.style.display = 'none';
        }
        if (!userMenuBtn.contains(e.target) && !userMenuPanel.contains(e.target)) {
            userMenuPanel.style.display = 'none';
        }
    });

    // Dashboard
    const updateDashboard = async () => {
        const weekStart = getWeekStart();
        document.getElementById('currentWeek').textContent = `Week of ${formatDateRange(weekStart)}`;
        
        try {
            const response = await fetch('/api/availability/status', {
                headers: { 'Authorization': `Bearer ${document.cookie.split('access_token=')[1]}` }
            });
            const data = await response.json();
            const statusBadge = document.getElementById('availabilityStatus');
            statusBadge.className = 'status-badge';
            statusBadge.innerHTML = data.submitted ? 
                '<i class="fas fa-check-circle"></i> Submitted' :
                '<i class="fas fa-exclamation-circle"></i> Not submitted';
            statusBadge.classList.add(data.submitted ? 'status-submitted' : 'status-missing');
            
            if (data.submitted) {
                const perfResponse = await fetch('/api/performance', {
                    headers: { 'Authorization': `Bearer ${document.cookie.split('access_token=')[1]}` }
                });
                const perfData = await perfResponse.json();
                document.getElementById('plannedHours').textContent = `${perfData.planned_hours}h`;
                document.getElementById('performanceStatus').textContent = 
                    perfData.variance <= 0 ? 'Good' : 'Needs Attention';
            }
        } catch (error) {
            console.error('Error updating dashboard:', error);
        }
    };

    // Availability
    const availabilityForm = document.getElementById('availabilityForm');
    const updateAvailabilityTab = () => {
        const weekStart = getWeekStart();
        document.getElementById('availabilityWeek').textContent = `Week of ${formatDateRange(weekStart)}`;
        document.getElementById('week-start').value = weekStart.toISOString().split('T')[0];

        const updateTotalHours = () => {
            const hours = ['monday', 'tuesday', 'wednesday', 'thursday'].reduce((sum, day) => {
                const input = document.getElementById(`${day}-hours`);
                return sum + (input && document.getElementById(`${day}-available`).checked ? parseInt(input.value) || 0 : 0);
            }, 0);
            document.getElementById('totalHours').textContent = `${hours}h`;
            const warning = document.getElementById('hoursWarning');
            warning.style.display = hours !== 36 ? 'flex' : 'none';
        };

        ['monday', 'tuesday', 'wednesday', 'thursday'].forEach(day => {
            const checkbox = document.getElementById(`${day}-available`);
            const hoursInput = document.getElementById(`${day}-hours`);
            checkbox.addEventListener('change', () => {
                hoursInput.disabled = !checkbox.checked;
                updateTotalHours();
            });
            hoursInput.addEventListener('input', updateTotalHours);
        });

        updateTotalHours();
    };

    availabilityForm?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData();
        formData.append('week_start', document.getElementById('week-start').value);
        ['monday', 'tuesday', 'wednesday', 'thursday'].forEach(day => {
            formData.append(`${day}_available`, document.getElementById(`${day}-available`).checked);
            formData.append(`${day}_hours`, document.getElementById(`${day}-hours`).value || '0');
            formData.append(`${day}_notes`, document.getElementById(`${day}-notes`).value);
        });

        try {
            const response = await fetch('/api/availability', {
                method: 'POST',
                body: formData,
                headers: { 'Authorization': `Bearer ${document.cookie.split('access_token=')[1]}` }
            });
            if (response.ok) {
                alert('Availability submitted successfully');
                document.querySelector('.nav-tab[data-tab="dashboard"]').click();
            } else {
                const error = await response.json();
                alert(`Error: ${error.detail}`);
            }
        } catch (error) {
            alert('Error submitting availability');
        }
    });

    // Performance
    const updatePerformanceTab = async () => {
        const weekStart = getWeekStart();
        document.getElementById('performanceWeek').textContent = `Week of ${formatDateRange(weekStart)}`;

        try {
            const response = await fetch('/api/performance', {
                headers: { 'Authorization': `Bearer ${document.cookie.split('access_token=')[1]}` }
            });
            const data = await response.json();
            document.getElementById('metricPlanned').textContent = `${data.planned_hours}h`;
            document.getElementById('metricActual').textContent = `${data.actual_hours}h`;
            document.getElementById('metricVariance').textContent = `${data.variance}%`;
            document.getElementById('metricDays').textContent = `${data.days_worked}/4`;

            const summaryList = document.getElementById('weeklySummaryList');
            summaryList.innerHTML = data.summary.length ? data.summary.map(item => `
                <div class="summary-item">
                    <strong>${item.day}:</strong> ${item.hours}h ${item.notes ? `- ${item.notes}` : ''}
                </div>
            `).join('') : '<div class="no-data">No performance data available for this week</div>';

            document.getElementById('aiFeedbackText').textContent = data.feedback;
        } catch (error) {
            console.error('Error updating performance:', error);
        }
    };

    document.getElementById('refreshFeedbackBtn')?.addEventListener('click', async () => {
        const feedbackText = document.getElementById('aiFeedbackText');
        const feedbackLoading = document.getElementById('feedbackLoading');
        feedbackLoading.style.display = 'block';
        feedbackText.style.display = 'none';

        try {
            const response = await fetch('/api/performance', {
                headers: { 'Authorization': `Bearer ${document.cookie.split('access_token=')[1]}` }
            });
            const data = await response.json();
            feedbackText.textContent = data.feedback;
        } catch (error) {
            feedbackText.textContent = 'Error generating feedback';
        } finally {
            feedbackLoading.style.display = 'none';
            feedbackText.style.display = 'block';
        }
    });

    // AI Settings
    const checkOllamaStatus = async () => {
        const statusSpan = document.getElementById('connectionStatus').querySelector('span');
        const modelSelection = document.getElementById('modelSelection');
        const setupInstructions = document.getElementById('setupInstructions');
        const modelInfo = document.getElementById('modelInfo');

        try {
            const response = await fetch('/api/ai-settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${document.cookie.split('access_token=')[1]}`
                },
                body: JSON.stringify({ prompt: 'Check connection' })
            });
            const data = await response.json();
            statusSpan.textContent = 'Connected';
            statusSpan.parentElement.classList.add('status-connected');
            setupInstructions.style.display = 'none';
            modelSelection.style.display = 'block';
            modelInfo.style.display = 'block';

            // Mock model selection (replace with actual Ollama API call if available)
            const modelSelect = document.getElementById('modelSelect');
            modelSelect.innerHTML = '<option value="llama3">llama3</option>';
            document.getElementById('currentModel').textContent = 'llama3';
            document.getElementById('modelCount').textContent = '1';
        } catch (error) {
            statusSpan.textContent = 'Not Connected';
            statusSpan.parentElement.classList.add('status-disconnected');
            setupInstructions.style.display = 'block';
            modelSelection.style.display = 'none';
            modelInfo.style.display = 'none';
        }
    };

    document.getElementById('refreshStatusBtn')?.addEventListener('click', checkOllamaStatus);

    // Quick Actions
    document.querySelector('.action-card[data-action="availability"]')?.addEventListener('click', () => {
        document.querySelector('.nav-tab[data-tab="availability"]').click();
    });

    // Login Form
    const loginForm = document.getElementById('loginForm');
    loginForm?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(loginForm);
        try {
            const response = await fetch('/login', {
                method: 'POST',
                body: formData
            });
            if (response.ok) {
                window.location.href = '/dashboard';
            } else {
                const error = await response.json();
                document.getElementById('loginError').textContent = error.detail;
            }
        } catch (error) {
            document.getElementById('loginError').textContent = 'Error logging in';
        }
    });

    // Initial load
    if (document.getElementById('dashboardScreen')) {
        updateDashboard();
    } else if (document.getElementById('loginScreen')) {
        document.getElementById('email').focus();
    }
});