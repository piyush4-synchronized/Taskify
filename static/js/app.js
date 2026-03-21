/**
 * app.js — Taskify Frontend Logic
 * Handles task CRUD, filtering, search, dark mode, and dynamic rendering.
 */

// ══════════════════════════════════════════════════════════════
//  STATE
// ══════════════════════════════════════════════════════════════
let allTasks = [];
let filters = {
    status: 'all',
    priority: 'all',
    category: 'all',
    search: ''
};

// Wobbly border-radius variants to randomly assign to task cards
const wobblyRadii = [
    '255px 15px 225px 15px / 15px 225px 15px 255px',
    '15px 255px 15px 225px / 225px 15px 255px 15px',
    '225px 15px 255px 15px / 15px 255px 15px 225px',
    '15px 225px 15px 255px / 255px 15px 225px 15px'
];

// ══════════════════════════════════════════════════════════════
//  INIT
// ══════════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
    loadTasks();
    setupAddForm();
    setupFilters();
    setupSearch();
    setupEditModal();
    setupDarkMode();
});

// ══════════════════════════════════════════════════════════════
//  API HELPERS
// ══════════════════════════════════════════════════════════════

async function apiFetch(url, options = {}) {
    const defaults = {
        headers: { 'Content-Type': 'application/json' }
    };
    const res = await fetch(url, { ...defaults, ...options });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Request failed');
    return data;
}

// ══════════════════════════════════════════════════════════════
//  LOAD & RENDER TASKS
// ══════════════════════════════════════════════════════════════

async function loadTasks() {
    try {
        allTasks = await apiFetch('/api/tasks');
        renderTasks();
    } catch (err) {
        console.error('Failed to load tasks:', err);
    }
}

function renderTasks() {
    const container = document.getElementById('tasks-container');
    const emptyState = document.getElementById('empty-state');

    // Apply filters
    let filtered = allTasks.filter(task => {
        // Status filter
        if (filters.status === 'completed' && !task.status) return false;
        if (filters.status === 'pending' && task.status) return false;

        // Priority filter
        if (filters.priority !== 'all' && task.priority !== filters.priority) return false;

        // Category filter
        if (filters.category !== 'all' && task.category !== filters.category) return false;

        // Search filter
        if (filters.search) {
            const q = filters.search.toLowerCase();
            const inTitle = task.title.toLowerCase().includes(q);
            const inDesc = (task.description || '').toLowerCase().includes(q);
            if (!inTitle && !inDesc) return false;
        }

        return true;
    });

    container.innerHTML = '';

    if (filtered.length === 0) {
        emptyState.style.display = 'block';
        return;
    }
    emptyState.style.display = 'none';

    filtered.forEach((task, i) => {
        container.appendChild(createTaskCard(task, i));
    });
}

function createTaskCard(task, index) {
    const card = document.createElement('div');
    card.className = 'task-card';
    card.style.borderRadius = wobblyRadii[index % wobblyRadii.length];

    // Mark completed
    if (task.status) card.classList.add('completed');

    // Check due date urgency
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    let dueTag = '';
    if (task.due_date && !task.status) {
        const due = new Date(task.due_date);
        due.setHours(0, 0, 0, 0);
        const diffDays = Math.ceil((due - today) / (1000 * 60 * 60 * 24));

        if (diffDays < 0) {
            card.classList.add('overdue');
            dueTag = `<span class="tag tag--overdue">⚠️ Overdue!</span>`;
        } else if (diffDays <= 2) {
            card.classList.add('due-soon');
            dueTag = `<span class="tag tag--due-soon">⏰ Due soon</span>`;
        }
    }

    const dueDateStr = task.due_date
        ? new Date(task.due_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
        : '';

    card.innerHTML = `
        <div class="task-header">
            <input type="checkbox" class="task-checkbox" 
                   ${task.status ? 'checked' : ''} 
                   data-id="${task.id}" title="Toggle completed">
            <span class="task-title">${escapeHTML(task.title)}</span>
        </div>
        ${task.description ? `<p class="task-desc">${escapeHTML(task.description)}</p>` : ''}
        <div class="task-meta">
            <span class="tag tag--priority-${task.priority}">${priorityIcon(task.priority)} ${task.priority}</span>
            <span class="tag tag--category">${categoryIcon(task.category)} ${task.category}</span>
            ${dueDateStr ? `<span class="tag tag--due">📅 ${dueDateStr}</span>` : ''}
            ${dueTag}
        </div>
        <div class="task-actions">
            <button class="btn btn-sm btn-secondary edit-btn" data-id="${task.id}"
                    style="border-radius: 255px 15px 225px 15px / 15px 225px 15px 255px;">
                ✏️ Edit
            </button>
            <button class="btn btn-sm delete-btn" data-id="${task.id}"
                    style="border-radius: 15px 255px 15px 225px / 225px 15px 255px 15px;">
                🗑️ Delete
            </button>
        </div>
    `;

    // Event: Toggle status
    card.querySelector('.task-checkbox').addEventListener('change', async (e) => {
        await toggleTaskStatus(task);
    });

    // Event: Edit
    card.querySelector('.edit-btn').addEventListener('click', () => openEditModal(task));

    // Event: Delete
    card.querySelector('.delete-btn').addEventListener('click', async () => {
        if (confirm(`Delete "${task.title}"?`)) {
            await deleteTask(task.id);
        }
    });

    return card;
}

// ══════════════════════════════════════════════════════════════
//  ADD TASK
// ══════════════════════════════════════════════════════════════

function setupAddForm() {
    document.getElementById('add-task-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const title = document.getElementById('task-title').value.trim();
        const description = document.getElementById('task-desc').value.trim();
        const priority = document.getElementById('task-priority').value;
        const category = document.getElementById('task-category').value;
        const due_date = document.getElementById('task-due').value || null;

        if (!title) return;

        try {
            await apiFetch('/api/tasks', {
                method: 'POST',
                body: JSON.stringify({ title, description, priority, category, due_date })
            });
            document.getElementById('add-task-form').reset();
            await loadTasks();
        } catch (err) {
            alert(err.message);
        }
    });
}

// ══════════════════════════════════════════════════════════════
//  UPDATE / DELETE TASK
// ══════════════════════════════════════════════════════════════

async function toggleTaskStatus(task) {
    try {
        await apiFetch(`/api/tasks/${task.id}`, {
            method: 'PUT',
            body: JSON.stringify({
                title: task.title,
                description: task.description,
                priority: task.priority,
                category: task.category,
                due_date: task.due_date,
                status: !task.status  // toggle
            })
        });
        await loadTasks();
    } catch (err) {
        alert(err.message);
    }
}

async function deleteTask(id) {
    try {
        await apiFetch(`/api/tasks/${id}`, { method: 'DELETE' });
        await loadTasks();
    } catch (err) {
        alert(err.message);
    }
}

// ══════════════════════════════════════════════════════════════
//  EDIT MODAL
// ══════════════════════════════════════════════════════════════

function setupEditModal() {
    document.getElementById('cancel-edit').addEventListener('click', closeEditModal);
    document.getElementById('edit-modal').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) closeEditModal();
    });

    document.getElementById('edit-task-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const id = document.getElementById('edit-task-id').value;
        const title = document.getElementById('edit-title').value.trim();
        const description = document.getElementById('edit-desc').value.trim();
        const priority = document.getElementById('edit-priority').value;
        const category = document.getElementById('edit-category').value;
        const due_date = document.getElementById('edit-due').value || null;

        // Find current task to preserve status
        const current = allTasks.find(t => t.id === parseInt(id));
        const status = current ? current.status : false;

        if (!title) return;

        try {
            await apiFetch(`/api/tasks/${id}`, {
                method: 'PUT',
                body: JSON.stringify({ title, description, priority, category, due_date, status })
            });
            closeEditModal();
            await loadTasks();
        } catch (err) {
            alert(err.message);
        }
    });
}

function openEditModal(task) {
    document.getElementById('edit-task-id').value = task.id;
    document.getElementById('edit-title').value = task.title;
    document.getElementById('edit-desc').value = task.description || '';
    document.getElementById('edit-priority').value = task.priority;
    document.getElementById('edit-category').value = task.category;
    document.getElementById('edit-due').value = task.due_date || '';
    document.getElementById('edit-modal').style.display = 'flex';
}

function closeEditModal() {
    document.getElementById('edit-modal').style.display = 'none';
}

// ══════════════════════════════════════════════════════════════
//  FILTERS
// ══════════════════════════════════════════════════════════════

function setupFilters() {
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const filterType = btn.dataset.filter;
            const value = btn.dataset.value;

            // Update state
            filters[filterType] = value;

            // Update active class within this group
            document.querySelectorAll(`.filter-btn[data-filter="${filterType}"]`).forEach(b => {
                b.classList.remove('active');
            });
            btn.classList.add('active');

            renderTasks();
        });
    });
}

// ══════════════════════════════════════════════════════════════
//  SEARCH
// ══════════════════════════════════════════════════════════════

function setupSearch() {
    const searchInput = document.getElementById('search-input');
    if (!searchInput) return;

    let debounce;
    searchInput.addEventListener('input', () => {
        clearTimeout(debounce);
        debounce = setTimeout(() => {
            filters.search = searchInput.value.trim();
            renderTasks();
        }, 250);
    });
}

// ══════════════════════════════════════════════════════════════
//  DARK MODE
// ══════════════════════════════════════════════════════════════

function setupDarkMode() {
    const toggle = document.getElementById('dark-mode-toggle');
    if (!toggle) return;

    // Load saved preference
    if (localStorage.getItem('taskify-dark') === 'true') {
        document.body.classList.add('dark');
        toggle.textContent = '☀️';
    }

    toggle.addEventListener('click', () => {
        document.body.classList.toggle('dark');
        const isDark = document.body.classList.contains('dark');
        toggle.textContent = isDark ? '☀️' : '🌙';
        localStorage.setItem('taskify-dark', isDark);
    });
}

// ══════════════════════════════════════════════════════════════
//  UTILITIES
// ══════════════════════════════════════════════════════════════

function escapeHTML(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function priorityIcon(p) {
    return { High: '🔴', Medium: '🟡', Low: '🟢' }[p] || '';
}

function categoryIcon(c) {
    return { Personal: '🏠', Work: '💼', Study: '📚', Health: '💪', Other: '📌' }[c] || '📌';
}
