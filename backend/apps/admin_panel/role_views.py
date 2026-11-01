from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import Group, Permission
from django.db.models import Q, Prefetch
from django.core.paginator import Paginator

from .decorators import superuser_required, sensitive_action_required
from .forms import RoleForm


@superuser_required
def access_control(request):
    tab = request.GET.get('tab', 'roles')
    
    if request.method == 'POST' and request.POST.get('action') == 'update_matrix':
        roles = Group.objects.all()
        for role in roles:
            perm_ids = request.POST.getlist(f'perms_{role.id}')
            role.permissions.set(perm_ids)
        messages.success(request, 'Permissions updated successfully.')
        return redirect('admin_panel:access_control' + ('?tab=matrix' if tab == 'matrix' else '?tab=matrix'))
    
    roles = Group.objects.all().prefetch_related('permissions').order_by('name')
    permissions = Permission.objects.all().select_related('content_type').order_by('content_type__app_label', 'codename')
    apps = Permission.objects.values_list('content_type__app_label', flat=True).distinct().order_by('content_type__app_label')
    
    # Group permissions by app
    permissions_by_app = {}
    for perm in permissions:
        app_label = perm.content_type.app_label
        if app_label not in permissions_by_app:
            permissions_by_app[app_label] = []
        permissions_by_app[app_label].append(perm)
    
    search = request.GET.get('q', '')
    app_filter = request.GET.get('app', '')
    if search and tab == 'permissions':
        permissions_qs = Permission.objects.all().select_related('content_type').filter(
            Q(codename__icontains=search) | Q(name__icontains=search)
        ).order_by('content_type__app_label', 'codename')
        if app_filter:
            permissions_qs = permissions_qs.filter(content_type__app_label=app_filter)
        paginator = Paginator(permissions_qs, 50)
        page_obj = paginator.get_page(request.GET.get('page'))
        return render(request, 'admin_panel/roles/access_control.html', {
            'tab': tab,
            'roles': roles,
            'permissions_by_app': permissions_by_app,
            'permissions': page_obj,
            'page_obj': page_obj,
            'search': search,
            'app_filter': app_filter,
            'apps': apps,
        })
    
    if app_filter and tab == 'permissions':
        permissions_qs = Permission.objects.all().select_related('content_type').filter(
            content_type__app_label=app_filter
        ).order_by('content_type__app_label', 'codename')
        paginator = Paginator(permissions_qs, 50)
        page_obj = paginator.get_page(request.GET.get('page'))
        return render(request, 'admin_panel/roles/access_control.html', {
            'tab': tab,
            'roles': roles,
            'permissions_by_app': permissions_by_app,
            'permissions': page_obj,
            'page_obj': page_obj,
            'search': search,
            'app_filter': app_filter,
            'apps': apps,
        })
    
    return render(request, 'admin_panel/roles/access_control.html', {
        'tab': tab,
        'roles': roles,
        'permissions_by_app': permissions_by_app,
        'apps': apps,
        'search': search,
        'app_filter': app_filter,
    })


@superuser_required
def role_list(request):
    queryset = Group.objects.all().prefetch_related('permissions').order_by('name')
    search = request.GET.get('q', '')
    if search:
        queryset = queryset.filter(name__icontains=search)
    paginator = Paginator(queryset, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_panel/roles/list.html', {
        'page_obj': page_obj,
        'roles': page_obj,
        'search': search,
    })


@superuser_required
def role_create(request):
    if request.method == 'POST':
        form = RoleForm(request.POST)
        if form.is_valid():
            role = form.save()
            # Handle permissions from checkbox group
            perm_ids = request.POST.getlist('permissions')
            if perm_ids:
                role.permissions.set(perm_ids)
            else:
                role.permissions.clear()
            messages.success(request, 'Role created successfully.')
            return redirect('admin_panel:role_list')
    else:
        form = RoleForm()
    permissions = Permission.objects.all().select_related('content_type').order_by('content_type__app_label', 'codename')
    return render(request, 'admin_panel/roles/create.html', {'form': form, 'permissions': permissions})


@sensitive_action_required
@superuser_required
def role_edit(request, pk):
    role = get_object_or_404(Group, pk=pk)
    if request.method == 'POST':
        form = RoleForm(request.POST, instance=role)
        if form.is_valid():
            role = form.save()
            perm_ids = request.POST.getlist('permissions')
            if perm_ids:
                role.permissions.set(perm_ids)
            else:
                role.permissions.clear()
            messages.success(request, 'Role updated successfully.')
            return redirect('admin_panel:role_list')
    else:
        form = RoleForm(instance=role)
    permissions = Permission.objects.all().select_related('content_type').order_by('content_type__app_label', 'codename')
    return render(request, 'admin_panel/roles/edit.html', {'form': form, 'role': role, 'permissions': permissions})


@sensitive_action_required
@superuser_required
def role_delete(request, pk):
    if request.method == 'POST':
        role = get_object_or_404(Group, pk=pk)
        role.delete()
        messages.success(request, 'Role deleted successfully.')
    return redirect('admin_panel:role_list')


@superuser_required
def permission_list(request):
    permissions = Permission.objects.all().select_related('content_type').order_by('content_type__app_label', 'codename')
    return render(request, 'admin_panel/roles/permissions.html', {'permissions': permissions})
