const API = {
    getSuppliers: (params = {}) => {
        const query = new URLSearchParams(params).toString();
        return fetch(`/api/suppliers?${query}`).then(r => r.json());
    },
    getSupplier: (id) => fetch(`/api/supplier/${id}`).then(r => r.json()),
    getSupplierPerformance: (id) => fetch(`/api/supplier/${id}/performance`).then(r => r.json()),
    getSupplierQualityIssues: (id) => fetch(`/api/supplier/${id}/quality_issues`).then(r => r.json()),
    getSupplierLogs: (id) => fetch(`/api/supplier/${id}/logs`).then(r => r.json()),
    getSupplierQualifications: (id) => fetch(`/api/supplier/${id}/qualifications`).then(r => r.json()),
    getPendingSuppliers: () => fetch('/api/pending_suppliers').then(r => r.json()),
    getReminderTasks: () => fetch('/api/tasks/reminders').then(r => r.json()),
    getApprovalTasks: () => fetch('/api/tasks/approvals').then(r => r.json()),
    getReports: () => fetch('/api/reports').then(r => r.json()),
    approveLevelChange: (id, approver) => {
        const form = new FormData();
        form.append('approver', approver);
        return fetch(`/api/approve_level_change/${id}`, { method: 'POST', body: form }).then(r => r.json());
    },
    createSupplier: (data) => {
        return fetch('/api/supplier/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        }).then(r => r.json());
    },
    uploadQualification: (supplierId, qualType, file) => {
        const form = new FormData();
        form.append('supplier_id', supplierId);
        form.append('qual_type', qualType);
        form.append('file', file);
        return fetch('/api/upload_qualification', { method: 'POST', body: form }).then(r => r.json());
    },
    reviewSupplier: (id) => {
        return fetch(`/api/review/${id}`, { method: 'POST' }).then(r => r.json());
    },
    exportSuppliers: (ids) => {
        return fetch('/api/export_suppliers', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids })
        }).then(r => {
            if (r.headers.get('content-type')?.includes('application/json')) {
                return r.json();
            }
            return r.blob().then(blob => ({ blob, filename: '供应商导出.xlsx' }));
        });
    },
    generateReport: (id) => fetch(`/api/generate_report/${id}`).then(r => r.json()),
    runDailyTasks: () => fetch('/api/daily_tasks', { method: 'POST' }).then(r => r.json()),
    downloadReport: (path) => `/api/download_report?path=${encodeURIComponent(path)}`
};

const Utils = {
    formatDate: (dateStr) => {
        if (!dateStr) return '-';
        const d = new Date(dateStr);
        if (isNaN(d.getTime())) return dateStr;
        return d.toLocaleDateString('zh-CN');
    },
    formatDateTime: (dateStr) => {
        if (!dateStr) return '-';
        const d = new Date(dateStr);
        if (isNaN(d.getTime())) return dateStr;
        return d.toLocaleString('zh-CN');
    },
    formatMoney: (amount) => {
        if (amount === null || amount === undefined) return '-';
        return '¥' + Number(amount).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    },
    getLevelBadge: (level) => {
        if (!level) return '<span class="badge">未评级</span>';
        return `<span class="badge badge-${level}">${level}级</span>`;
    },
    getStatusBadge: (status) => {
        const map = {
            'approved': 'badge-approved',
            'pending': 'badge-pending',
            'rejected': 'badge-rejected',
            'suspended': 'badge-suspended',
            'abandoned': 'badge-abandoned'
        };
        const labels = {
            'approved': '已通过',
            'pending': '待审核',
            'rejected': '已拒绝',
            'suspended': '已暂停',
            'abandoned': '已放弃'
        };
        return `<span class="badge ${map[status] || ''}">${labels[status] || status}</span>`;
    },
    getSeverityBadge: (severity) => {
        const map = {
            'major': 'badge-major',
            'normal': 'badge-minor'
        };
        const labels = {
            'major': '重大',
            'normal': '一般'
        };
        return `<span class="badge ${map[severity] || ''}">${labels[severity] || severity}</span>`;
    },
    getPriorityBadge: (priority) => {
        const map = {
            'high': 'badge-high',
            'medium': 'badge-medium',
            'normal': 'badge-normal',
            'low': 'badge-low'
        };
        const labels = {
            'high': '高',
            'medium': '中',
            'normal': '普通',
            'low': '低'
        };
        return `<span class="badge ${map[priority] || ''}">${labels[priority] || priority}</span>`;
    },
    getScoreBar: (score) => {
        let cls = 'poor';
        if (score >= 90) cls = 'excellent';
        else if (score >= 80) cls = 'good';
        else if (score >= 70) cls = 'average';
        return `<div class="score-bar"><div class="score-fill ${cls}" style="width: ${Math.min(100, score)}%"></div></div>`;
    },
    showMessage: (message, type = 'info') => {
        const alert = document.createElement('div');
        alert.className = `alert alert-${type}`;
        alert.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 9999; max-width: 400px;';
        alert.textContent = message;
        document.body.appendChild(alert);
        setTimeout(() => alert.remove(), 3000);
    },
    showModal: (modalId) => {
        document.getElementById(modalId)?.classList.add('active');
    },
    hideModal: (modalId) => {
        document.getElementById(modalId)?.classList.remove('active');
    },
    downloadBlob: (blob, filename) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    },
    initTabs: () => {
        document.querySelectorAll('.tabs').forEach(tabs => {
            const tabItems = tabs.querySelectorAll('.tab');
            const contentIds = Array.from(tabItems).map(t => t.dataset.tab);
            tabItems.forEach(tab => {
                tab.addEventListener('click', () => {
                    tabItems.forEach(t => t.classList.remove('active'));
                    tab.classList.add('active');
                    contentIds.forEach(id => {
                        document.getElementById(id)?.classList.remove('active');
                    });
                    document.getElementById(tab.dataset.tab)?.classList.add('active');
                });
            });
        });
    }
};

document.addEventListener('DOMContentLoaded', () => {
    Utils.initTabs();
    
    document.querySelectorAll('.close-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const modal = e.target.closest('.modal');
            modal?.classList.remove('active');
        });
    });
    
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.remove('active');
            }
        });
    });
});
