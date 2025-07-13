// Task List Component
function taskList(listType) {
    return {
        tasks: [],
        filteredTasks: [],  // Initialize as empty array instead of null
        searchQuery: '',
        showCompletedTasks: false,
        showTasksICreated: false,  // Add missing property
        currentUserId: null,
        isInitialized: false,  // Add initialization flag

        init() {
            try {
                // Get tasks data from the JSON embedded in the page
                const tasksDataElement = document.getElementById('tasks-data');
                if (!tasksDataElement) {
                    console.error('Tasks data element not found');
                    return;
                }

                const tasksData = JSON.parse(tasksDataElement.textContent);
                console.log('Tasks data:', tasksData); // Debug
                this.currentUserId = tasksData.currentUserId;

                // Initialize tasks based on list type
                if (listType === 'tasks-for-me') {
                    this.tasks = Array.from(tasksData.tasksForMe || []);
                    this.filteredTasks = this.sortTasksByPriority([...this.tasks]);
                } else if (listType === 'all-tasks') {
                    this.tasks = Array.from(tasksData.allTasks || []);
                    this.filteredTasks = this.sortTasksByPriority([...this.tasks]);
                } else if (listType === 'completed-tasks') {
                    console.log('Loading completed tasks'); // Debug
                    this.tasks = Array.from(tasksData.completedTasks || []);
                    this.filteredTasks = [...this.tasks]; // No need to sort completed tasks by flag
                    console.log('Completed tasks loaded:', this.tasks); // Debug
                }

                this.isInitialized = true;
                console.log('Task list initialized:', {
                    listType,
                    tasks: Array.from(this.tasks),
                    filteredTasks: Array.from(this.filteredTasks)
                }); // Debug
            } catch (error) {
                console.error('Error initializing task list:', error);
                this.tasks = [];
                this.filteredTasks = [];
            }
        },

        // Sort tasks with flagged tasks at the top
        sortTasksByPriority(tasks) {
            return tasks.sort((a, b) => {
                // First, sort by flagged status (flagged tasks first)
                if (a.is_flagged && !b.is_flagged) return -1;
                if (!a.is_flagged && b.is_flagged) return 1;

                // Then sort by creation date (newest first) within each group
                const dateA = new Date(a.created_at);
                const dateB = new Date(b.created_at);
                return dateB - dateA;
            });
        },

        // Filter tasks based on search query
        filterTasks() {
            if (!this.isInitialized) return;

            let filtered;
            if (!this.searchQuery.trim()) {
                filtered = [...this.tasks];
            } else {
                const query = this.searchQuery.toLowerCase();
                filtered = this.tasks.filter(task =>
                    task.description.toLowerCase().includes(query) ||
                    (task.project_name && task.project_name.toLowerCase().includes(query)) ||
                    (task.client_name && task.client_name.toLowerCase().includes(query)) ||
                    (task.assigned_to_name && task.assigned_to_name.toLowerCase().includes(query)) ||
                    (task.creator_name && task.creator_name.toLowerCase().includes(query))
                );
            }

            // Apply priority sorting to filtered results (except for completed tasks)
            if (listType !== 'completed-tasks') {
                this.filteredTasks = this.sortTasksByPriority(filtered);
            } else {
                this.filteredTasks = filtered;
            }
        },

        // Clear search
        clearSearch() {
            if (!this.isInitialized) return;
            this.searchQuery = '';

            // Apply priority sorting when clearing search (except for completed tasks)
            if (listType !== 'completed-tasks') {
                this.filteredTasks = this.sortTasksByPriority([...this.tasks]);
            } else {
                this.filteredTasks = [...this.tasks];
            }
        },

        // Group tasks by project
        getTasksByProject() {
            if (!this.isInitialized) return [];

            const projectGroups = {};

            this.filteredTasks.forEach(task => {
                const projectKey = task.project_name || 'No Project';
                const clientName = task.client_name || '';

                if (!projectGroups[projectKey]) {
                    projectGroups[projectKey] = {
                        id: task.project_id || 'no-project',
                        name: projectKey,
                        client_name: clientName,
                        tasks: []
                    };
                }

                projectGroups[projectKey].tasks.push(task);
            });

            // Sort tasks within each project group by priority
            Object.values(projectGroups).forEach(group => {
                group.tasks = this.sortTasksByPriority(group.tasks);
            });

            return Object.values(projectGroups);
        },

        // Computed property for projects (used by task_list_by_project.html)
        get projects() {
            if (!this.isInitialized) return [];
            return this.getTasksByProject();
        },

        // Toggle completed tasks visibility
        toggleCompletedTasks() {
            if (!this.isInitialized) return;
            this.showCompletedTasks = !this.showCompletedTasks;
        },

        // Toggle tasks I created visibility
        toggleTasksICreated() {
            if (!this.isInitialized) return;
            this.showTasksICreated = !this.showTasksICreated;
        },

        // Add task to specific project
        addTaskToProject(projectGroup) {
            if (!this.isInitialized) return;

            // Trigger the task modal with pre-selected project
            const event = new CustomEvent('open-task-modal', {
                detail: {
                    defaultProject: projectGroup.name === 'No Project' ? null : projectGroup.name
                }
            });
            window.dispatchEvent(event);
        },

        // Format date helper
        formatDate(dateString) {
            if (!dateString) return '';
            const date = new Date(dateString);
            return date.toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'short',
                day: 'numeric'
            });
        },

        // Edit task
        editTask(task) {
            if (!this.isInitialized || !task) return;

            // Trigger the task modal for editing
            const event = new CustomEvent('open-task-modal', {
                detail: {
                    task: task,
                    mode: 'edit'
                }
            });
            window.dispatchEvent(event);
        }
    }
}

// Log Entry Modal Alpine Component
function logEntryModal() {
    return {
        searchQuery: '',
        allProjects: [],
        filteredProjects: [],

        async loadProjects() {
            try {
                const response = await fetch('/api/projects_for_logging');
                const data = await response.json();
                this.allProjects = data.projects || [];
                this.filteredProjects = [...this.allProjects];
            } catch (error) {
                console.error('Failed to load projects:', error);
                this.allProjects = [];
                this.filteredProjects = [];
            }
        },

        filterProjects() {
            if (!this.searchQuery.trim()) {
                this.filteredProjects = [...this.allProjects];
                return;
            }

            const query = this.searchQuery.toLowerCase();
            this.filteredProjects = this.allProjects.filter(project =>
                project.name.toLowerCase().includes(query) ||
                project.client_name.toLowerCase().includes(query) ||
                project.display_name.toLowerCase().includes(query)
            );
        },

        async logTouch(projectId) {
            try {
                console.log('Logging touch for project ID:', projectId);

                const response = await fetch('/add_touch_log', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ project_id: projectId })
                });

                console.log('Response status:', response.status);
                const data = await response.json();
                console.log('Response data:', data);

                if (data.success) {
                    // Trigger confetti animation
                    if (typeof confetti === 'function') {
                        confetti({
                            particleCount: 100,
                            spread: 70,
                            origin: { y: 0.6 },
                            colors: ['#3498db', '#2ecc71', '#f39c12', '#e74c3c', '#9b59b6']
                        });
                    }

                    // Close modal
                    const modal = document.getElementById('logEntryModal');
                    const bsModal = bootstrap.Modal.getInstance(modal);
                    bsModal.hide();
                } else {
                    console.error('Failed to log touch:', data.error);
                    alert('Failed to log touch. Please try again.');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Error logging touch. Please try again.');
            }
        },

        openTimeLog(project) {
            // Close the log entry modal
            const logEntryModal = document.getElementById('logEntryModal');
            const bsLogEntryModal = bootstrap.Modal.getInstance(logEntryModal);
            bsLogEntryModal.hide();

            // Set project info in the time log form
            document.getElementById('timeLogProjectId').value = project.id;
            document.getElementById('timeLogProject').value = project.display_name;
        }
    }
}

// Task Form Component
function taskForm() {
    return {
        rawInput: '',
        selectedProject: {},
        selectedUser: {},
        projects: [],
        users: [],
        showAutocomplete: false,
        editMode: false,
        editTaskId: null,
        filteredItems: [],
        selectedIndex: -1,
        autocompleteType: null, // 'project' or 'user'
        currentQuery: '',

        init() {
            console.log('TaskForm initialized');
            this.loadData();
            this.setupEventListeners();

            // Focus the input after Alpine.js is fully initialized
            // Only focus if this is not inside a modal (main page task form)
            this.$nextTick(() => {
                const isInModal = this.$el.closest('.modal');
                if (!isInModal) {
                    // Use a longer delay to ensure all page initialization is complete
                    setTimeout(() => {
                        if (this.$refs.taskInput) {
                            this.$refs.taskInput.focus();
                            console.log('Task input focused');
                        }
                    }, 500);
                }
            });
        },

        async loadData() {
            try {
                // Load projects
                const projectsResponse = await fetch('/api/projects');
                const projectsData = await projectsResponse.json();
                this.projects = projectsData.projects || [];

                // Load users
                const usersResponse = await fetch('/api/users');
                const usersData = await usersResponse.json();
                this.users = usersData.users || [];

                // Set default project
                this.setDefaultProject();

            } catch (error) {
                console.error('Failed to load form data:', error);
            }
        },

        setDefaultProject() {
            // Look for a project marked as default first, then use the first project
            if (this.projects.length > 0) {
                const defaultProject = this.projects.find(p => p.is_default);
                this.selectedProject = defaultProject || this.projects[0];
                // Don't set rawInput - keep the text box empty
            }
        },

        setupEventListeners() {
            // Listen for preset project events
            this.$el.addEventListener('set-preset-project', (event) => {
                const { projectId, projectName, lookupByName } = event.detail;

                let project = null;
                if (lookupByName) {
                    project = this.projects.find(p => p.name === projectName);
                } else {
                    project = this.projects.find(p => p.id == projectId);
                }

                if (project) {
                    this.selectedProject = project;
                    // Don't set rawInput - keep the text box empty
                } else {
                    // Fallback - create a minimal project object
                    this.selectedProject = {
                        id: projectId,
                        name: projectName,
                        display_name: projectName
                    };
                    // Don't set rawInput - keep the text box empty
                }
            });

            // Listen for preset user events
            this.$el.addEventListener('set-preset-user', (event) => {
                const { userId, userName } = event.detail;

                const user = this.users.find(u => u.id == userId);
                if (user) {
                    this.selectedUser = user;
                    // Don't set rawInput - keep the text box empty
                } else {
                    // Fallback - create a minimal user object
                    this.selectedUser = {
                        id: userId,
                        name: userName
                    };
                    // Don't set rawInput - keep the text box empty
                }
            });

            // Listen for edit task events
            this.$el.addEventListener('set-edit-task', (event) => {
                const { taskId, description, projectId, projectName, userId, userName } = event.detail;

                this.editMode = true;
                this.editTaskId = taskId;
                this.rawInput = description;

                // Set project if provided
                if (projectId || projectName) {
                    let project = null;
                    if (projectId) {
                        project = this.projects.find(p => p.id == projectId);
                    } else if (projectName) {
                        project = this.projects.find(p => p.name === projectName);
                    }

                    if (project) {
                        this.selectedProject = project;
                    } else if (projectName) {
                        this.selectedProject = {
                            id: projectId,
                            name: projectName,
                            display_name: projectName
                        };
                    }
                }

                // Set user if provided
                if (userId || userName) {
                    let user = null;
                    if (userId) {
                        user = this.users.find(u => u.id == userId);
                    }

                    if (user) {
                        this.selectedUser = user;
                    } else if (userName) {
                        this.selectedUser = {
                            id: userId,
                            name: userName
                        };
                    }
                }
            });
        },

        parseInput() {
            const input = this.rawInput;
            const cursorPosition = this.$refs.taskInput ? this.$refs.taskInput.selectionStart : input.length;

            // Find the last # or @ before cursor
            let lastHashIndex = input.lastIndexOf('#', cursorPosition - 1);
            let lastAtIndex = input.lastIndexOf('@', cursorPosition - 1);

            // Check if we're in the middle of a tag
            let tagStart = Math.max(lastHashIndex, lastAtIndex);

            if (tagStart !== -1) {
                // Check if this is a bracket tag format like #[ProjectName] or @[UserName]
                let isBracketTag = input[tagStart + 1] === '[';
                let tagEnd;

                if (isBracketTag) {
                    // For bracket tags, find the closing bracket
                    tagEnd = input.indexOf(']', tagStart);
                    if (tagEnd === -1) tagEnd = input.length;
                    else tagEnd += 1; // Include the closing bracket
                } else {
                    // For non-bracket tags, find the next space
                    tagEnd = input.indexOf(' ', tagStart);
                    if (tagEnd === -1) tagEnd = input.length;
                }

                // If cursor is within the tag
                if (cursorPosition >= tagStart && cursorPosition <= tagEnd) {
                    let tagType = input[tagStart] === '#' ? 'project' : 'user';
                    let query;

                    if (isBracketTag) {
                        // Extract query from within brackets: #[query] or @[query]
                        query = input.substring(tagStart + 2, cursorPosition);
                    } else {
                        // Extract query from simple format: #query or @query
                        query = input.substring(tagStart + 1, cursorPosition);
                    }

                    this.showAutocomplete = true;
                    this.autocompleteType = tagType;
                    this.currentQuery = query;
                    this.filterItems(query, tagType);
                    this.selectedIndex = -1;
                    return;
                }
            }

            // Hide autocomplete if not in a tag
            this.showAutocomplete = false;
        },

        filterItems(query, type) {
            const lowerQuery = query.toLowerCase();

            if (type === 'project') {
                this.filteredItems = this.projects.filter(project =>
                    project.name.toLowerCase().includes(lowerQuery)
                ).slice(0, 10);
            } else if (type === 'user') {
                this.filteredItems = this.users.filter(user =>
                    user.name.toLowerCase().includes(lowerQuery)
                ).slice(0, 10);
            }
        },

        handleKeydown(event) {
            if (!this.showAutocomplete) return;

            switch (event.key) {
                case 'ArrowDown':
                    event.preventDefault();
                    this.selectedIndex = Math.min(this.selectedIndex + 1, this.filteredItems.length - 1);
                    break;
                case 'ArrowUp':
                    event.preventDefault();
                    this.selectedIndex = Math.max(this.selectedIndex - 1, -1);
                    break;
                case 'Enter':
                    event.preventDefault();
                    if (this.selectedIndex >= 0 && this.filteredItems[this.selectedIndex]) {
                        this.selectItem(this.filteredItems[this.selectedIndex]);
                    }
                    break;
                case 'Escape':
                    this.showAutocomplete = false;
                    this.selectedIndex = -1;
                    break;
            }
        },

        selectItem(item) {
            const input = this.rawInput;
            const cursorPosition = this.$refs.taskInput ? this.$refs.taskInput.selectionStart : input.length;

            // Find the tag start
            let tagStart = Math.max(
                input.lastIndexOf('#', cursorPosition - 1),
                input.lastIndexOf('@', cursorPosition - 1)
            );

            if (tagStart !== -1) {
                // Check if this is a bracket tag format
                let isBracketTag = input[tagStart + 1] === '[';
                let tagEnd;

                if (isBracketTag) {
                    // For bracket tags, find the closing bracket
                    tagEnd = input.indexOf(']', tagStart);
                    if (tagEnd === -1) tagEnd = input.length;
                    else tagEnd += 1; // Include the closing bracket
                } else {
                    // For non-bracket tags, find the next space
                    tagEnd = input.indexOf(' ', tagStart);
                    if (tagEnd === -1) tagEnd = input.length;
                }

                // Replace the partial tag with the selected item (always use bracket format)
                let prefix = input.substring(0, tagStart + 1);
                let suffix = input.substring(tagEnd);

                this.rawInput = prefix + '[' + item.name + ']' + suffix;

                // Update selected items
                if (this.autocompleteType === 'project') {
                    this.selectedProject = { id: item.id, name: item.name };
                } else if (this.autocompleteType === 'user') {
                    this.selectedUser = { id: item.id, name: item.name };
                }
            }

            this.showAutocomplete = false;
            this.selectedIndex = -1;

            // Focus back on input
            this.$nextTick(() => {
                if (this.$refs.taskInput) {
                    this.$refs.taskInput.focus();
                }
            });
        },

        resetForm() {
            this.rawInput = '';
            this.selectedProject = {};
            this.selectedUser = {};
            this.showAutocomplete = false;
            this.editMode = false;
            this.editTaskId = null;
            this.filteredItems = [];
            this.selectedIndex = -1;
            this.autocompleteType = null;
            this.currentQuery = '';
            this.setDefaultProject();
        },

        onSubmit(event) {
            // Debug: Log form data before submission
            console.log('DEBUG onSubmit: rawInput =', this.rawInput);
            console.log('DEBUG onSubmit: selectedProject =', this.selectedProject);
            console.log('DEBUG onSubmit: selectedUser =', this.selectedUser);

            // Store the original input for potential processing
            if (this.$refs.originalInput) {
                this.$refs.originalInput.value = this.rawInput;
            }

            // Ensure we have required data
            if (!this.rawInput.trim()) {
                console.log('DEBUG onSubmit: No description provided, preventing submission');
                event.preventDefault();
                return false;
            }

            console.log('DEBUG onSubmit: Form submission allowed');
            // Allow the form to submit naturally
            return true;
        },

        submitForm() {
            if (!this.rawInput.trim()) return;

            const form = this.$el.closest('form');
            if (form) {
                // Set the description field
                const descriptionField = form.querySelector('input[name="description"]');
                if (descriptionField) {
                    descriptionField.value = this.rawInput;
                }

                // Set project field
                const projectField = form.querySelector('input[name="project_id"]');
                if (projectField && this.selectedProject.id) {
                    projectField.value = this.selectedProject.id;
                }

                // Set user field
                const userField = form.querySelector('input[name="assigned_to"]');
                if (userField && this.selectedUser.id) {
                    userField.value = this.selectedUser.id;
                }

                // Change form action for edit mode
                if (this.editMode && this.editTaskId) {
                    form.action = `/task/${this.editTaskId}/edit`;
                }

                // Submit the form
                form.submit();
            }
        }
    }
}

// Task Item Data Helper (for use in templates)
function taskItemData(taskItem, variant = 'interactive', options = {}) {
    return {
        task: taskItem,
        variant: variant,
        showProject: options.showProject !== false,
        showAssignee: options.showAssignee !== false,
        showCreator: options.showCreator !== false,
        showActions: options.showActions !== false,
        showFlag: options.showFlag !== false,
        alwaysShowMetadata: options.alwaysShowMetadata || false,

        formatDate(dateString) {
            if (!dateString) return '';
            const date = new Date(dateString);
            return date.toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'short',
                day: 'numeric'
            });
        },

        editTask(task) {
            const modal = document.getElementById('taskModal');
            if (modal) {
                modal.dataset.editTaskId = task.id;
                modal.dataset.editDescription = task.description;
                modal.dataset.editProjectId = task.project_id || (task.project_name ? 'lookup' : '');
                modal.dataset.editProjectName = task.project_name || '';
                modal.dataset.editUserId = task.assigned_to_id || '';
                modal.dataset.editUserName = task.assigned_to_name || '';

                const bootstrapModal = new bootstrap.Modal(modal);
                bootstrapModal.show();
            }
        }
    }
}

// Make taskItemData available globally for Alpine.js templates
window.taskItemData = taskItemData; 