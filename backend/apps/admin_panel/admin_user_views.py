from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import Q
from django.core.paginator import Paginator

from .decorators import superuser_required, sensitive_action_required
from .forms import AdminUserForm

User = get_user_model()


@superuser_required
def admin_user_list(request):
    queryset = User.objects.filter(Q(is_staff=True) | Q(is_superuser=True)).order_by('-date_joined')
    search = request.GET.get('q', '')
    if search:
        queryset = queryset.filter(
            Q(email__icontains=search) | Q(first_name__icontains=search) | Q(last_name__icontains=search) | Q(phone_number__icontains=search)
        )
    paginator = Paginator(queryset, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_panel/admins/list.html', {
        'page_obj': page_obj,
        'users': page_obj,
        'search': search,
    })


@superuser_required
def admin_user_create(request):
    if request.method == 'POST':
        form = AdminUserForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_staff = True
            password = form.cleaned_data.get('password')
            if password:
                user.set_password(password)
            else:
                messages.error(request, 'Password is required for new admin user.')
                return render(request, 'admin_panel/admins/create.html', {'form': form})
            user.save()
            form.save_m2m()
            messages.success(request, 'Admin user created successfully.')
            return redirect('admin_panel:admin_user_list')
    else:
        form = AdminUserForm()
    return render(request, 'admin_panel/admins/create.html', {'form': form})


@sensitive_action_required
@superuser_required
def admin_user_edit(request, pk):
    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        form = AdminUserForm(request.POST, instance=user)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_staff = True
            password = form.cleaned_data.get('password')
            if password:
                user.set_password(password)
            user.save()
            form.save_m2m()
            messages.success(request, 'Admin user updated successfully.')
            return redirect('admin_panel:admin_user_list')
    else:
        form = AdminUserForm(instance=user)
    return render(request, 'admin_panel/admins/edit.html', {'form': form, 'user_obj': user})


@sensitive_action_required
@superuser_required
def admin_user_toggle(request, pk):
    if request.method == 'POST':
        user = get_object_or_404(User, pk=pk)
        if user == request.user:
            messages.error(request, 'You cannot deactivate your own account.')
            return redirect('admin_panel:admin_user_list')
        if user.is_superuser and User.objects.filter(is_superuser=True, is_active=True).count() <= 1:
            messages.error(request, 'Cannot deactivate the last active superuser.')
            return redirect('admin_panel:admin_user_list')
        user.is_active = not user.is_active
        user.save()
        messages.success(request, f'User {"activated" if user.is_active else "deactivated"} successfully.')
    return redirect('admin_panel:admin_user_list')
