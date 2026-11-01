from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import Group, Permission
from django.db.models import Q
from django.core.paginator import Paginator

from .decorators import superuser_required, sensitive_action_required
from .forms import RoleForm


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
