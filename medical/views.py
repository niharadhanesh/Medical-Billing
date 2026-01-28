from django.shortcuts import render
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.auth import logout

def landing_page(request):
    return render(request, "landing.html")

def dashboard(request):
    return render(request,"dashboard.html")

def user_dashboard(request):
    return render(request,"user_dashboard.html")

from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.shortcuts import render, redirect

def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            # 🔐 Role-based redirection
            if user.is_superuser:
                return redirect("dashboard")          # Admin dashboard
            else:
                return redirect("user_dashboard")     # Staff/User dashboard

        else:
            messages.error(request, "Invalid username or password")

    return render(request, "login.html")

def logout_view(request):
    logout(request)  # logs out the user
    messages.success(request, "You have been logged out successfully.")
    return redirect("landing") 

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import Medicine, StockTransaction
from datetime import datetime

@login_required
def add_medicine(request, pk=None):
    # Check if we're editing an existing medicine
    medicine = None
    if pk:
        medicine = get_object_or_404(Medicine, pk=pk)
    
    if request.method == 'POST':
        try:
            if medicine:
                # Editing existing medicine - Store old quantity BEFORE any changes
                old_quantity = medicine.quantity
                
                # Update all fields
                medicine.name = request.POST.get('name')
                medicine.generic_name = request.POST.get('generic_name')
                medicine.category = request.POST.get('category')
                medicine.manufacturer = request.POST.get('manufacturer')
                medicine.description = request.POST.get('description')
                medicine.reorder_level = int(request.POST.get('reorder_level', 10))
                medicine.unit_price = float(request.POST.get('unit_price'))
                medicine.selling_price = float(request.POST.get('selling_price'))
                medicine.manufacturing_date = request.POST.get('manufacturing_date')
                medicine.expiry_date = request.POST.get('expiry_date')
                medicine.batch_number = request.POST.get('batch_number')
                medicine.rack_number = request.POST.get('rack_number')
                
                # Handle quantity separately
                new_quantity = int(request.POST.get('quantity', 0))
                medicine.quantity = new_quantity
                
                # Save the medicine
                medicine.save()
                
                # Log stock change if quantity changed
                if old_quantity != new_quantity:
                    quantity_diff = new_quantity - old_quantity
                    StockTransaction.objects.create(
                        medicine=medicine,
                        transaction_type='purchase' if quantity_diff > 0 else 'sale',
                        quantity=abs(quantity_diff),
                        price_per_unit=medicine.unit_price,
                        notes=f'Stock adjusted from {old_quantity} to {new_quantity} via edit',
                        performed_by=request.user
                    )
                
                messages.success(request, f'Medicine "{medicine.name}" updated successfully! Stock: {new_quantity} units')
            else:
                # Creating new medicine
                medicine = Medicine.objects.create(
                    name=request.POST.get('name'),
                    generic_name=request.POST.get('generic_name'),
                    category=request.POST.get('category'),
                    manufacturer=request.POST.get('manufacturer'),
                    description=request.POST.get('description'),
                    quantity=int(request.POST.get('quantity', 0)),
                    reorder_level=int(request.POST.get('reorder_level', 10)),
                    unit_price=float(request.POST.get('unit_price')),
                    selling_price=float(request.POST.get('selling_price')),
                    manufacturing_date=request.POST.get('manufacturing_date'),
                    expiry_date=request.POST.get('expiry_date'),
                    batch_number=request.POST.get('batch_number'),
                    rack_number=request.POST.get('rack_number'),
                    created_by=request.user
                )
                
                # Create initial stock transaction
                if medicine.quantity > 0:
                    StockTransaction.objects.create(
                        medicine=medicine,
                        transaction_type='purchase',
                        quantity=medicine.quantity,
                        price_per_unit=medicine.unit_price,
                        notes='Initial stock',
                        performed_by=request.user
                    )
                
                messages.success(request, f'Medicine "{medicine.name}" added successfully! Initial stock: {medicine.quantity} units')
            
            return redirect('medicine_stock')
        except Exception as e:
            messages.error(request, f'Error {"updating" if pk else "adding"} medicine: {str(e)}')
            # If there's an error during edit, reload the medicine to show current data
            if pk:
                medicine = get_object_or_404(Medicine, pk=pk)
    
    context = {
        'categories': Medicine.CATEGORY_CHOICES,
        'medicine': medicine,
        'is_edit': medicine is not None,
    }
    return render(request, 'add_medicine.html', context)


@login_required
def medicine_stock(request):
    # Get filter parameters
    search_query = request.GET.get('search', '')
    category_filter = request.GET.get('category', '')
    stock_filter = request.GET.get('stock_status', '')
    
    # Base queryset
    medicines = Medicine.objects.all()
    
    # Apply search
    if search_query:
        medicines = medicines.filter(
            Q(name__icontains=search_query) |
            Q(generic_name__icontains=search_query) |
            Q(manufacturer__icontains=search_query)
        )
    
    # Apply category filter
    if category_filter:
        medicines = medicines.filter(category=category_filter)
    
    # Apply stock status filter
    if stock_filter == 'low':
        medicines = [m for m in medicines if m.is_low_stock and not m.is_expired]
    elif stock_filter == 'expired':
        medicines = [m for m in medicines if m.is_expired]
    elif stock_filter == 'out':
        medicines = medicines.filter(quantity=0)
    
    # Calculate stats
    total_medicines = Medicine.objects.count()
    low_stock_count = len([m for m in Medicine.objects.all() if m.is_low_stock])
    expired_count = len([m for m in Medicine.objects.all() if m.is_expired])
    out_of_stock = Medicine.objects.filter(quantity=0).count()
    
    context = {
        'medicines': medicines,
        'categories': Medicine.CATEGORY_CHOICES,
        'search_query': search_query,
        'category_filter': category_filter,
        'stock_filter': stock_filter,
        'total_medicines': total_medicines,
        'low_stock_count': low_stock_count,
        'expired_count': expired_count,
        'out_of_stock': out_of_stock,
    }
    return render(request, 'medicine_stock.html', context)


@login_required
def delete_medicine(request, pk):
    medicine = get_object_or_404(Medicine, pk=pk)
    
    if request.method == 'POST':
        name = medicine.name
        medicine.delete()
        messages.success(request, f'Medicine "{name}" deleted successfully!')
        return redirect('medicine_stock')
    
    return redirect('medicine_stock')


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Sum, Count
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.utils import timezone
from decimal import Decimal
import json

from .models import Medicine, Bill, BillItem, Customer, StockTransaction


@login_required
def billing_page(request):
    """Main billing page"""
    return render(request, 'billing.html')


@login_required
def search_medicine_ajax(request):
    """AJAX endpoint to search medicines"""
    query = request.GET.get('q', '')
    
    if len(query) < 2:
        return JsonResponse({'medicines': []})
    
    medicines = Medicine.objects.filter(
        Q(name__icontains=query) | 
        Q(generic_name__icontains=query) |
        Q(batch_number__icontains=query)
    ).filter(
        quantity__gt=0,  # Only in-stock medicines
        expiry_date__gt=timezone.now().date()  # Not expired
    )[:10]  # Limit to 10 results
    
    data = [{
        'id': m.id,
        'name': m.name,
        'generic_name': m.generic_name,
        'batch_number': m.batch_number,
        'category': m.get_category_display(),
        'selling_price': str(m.selling_price),
        'available_quantity': m.quantity,
        'manufacturer': m.manufacturer,
        'expiry_date': m.expiry_date.strftime('%Y-%m-%d')
    } for m in medicines]
    
    return JsonResponse({'medicines': data})


@login_required
def get_medicine_details(request, medicine_id):
    """Get detailed information about a specific medicine"""
    medicine = get_object_or_404(Medicine, id=medicine_id)
    
    data = {
        'id': medicine.id,
        'name': medicine.name,
        'generic_name': medicine.generic_name,
        'batch_number': medicine.batch_number,
        'category': medicine.get_category_display(),
        'selling_price': str(medicine.selling_price),
        'available_quantity': medicine.quantity,
        'manufacturer': medicine.manufacturer,
        'expiry_date': medicine.expiry_date.strftime('%Y-%m-%d'),
        'rack_number': medicine.rack_number
    }
    
    return JsonResponse(data)


@login_required
@require_http_methods(["POST"])
def create_bill(request):
    """Create a new bill"""
    try:
        data = json.loads(request.body)
        
        # Validate bill items
        if not data.get('items') or len(data['items']) == 0:
            return JsonResponse({
                'success': False,
                'message': 'Please add at least one item to the bill'
            }, status=400)
        
        # Create or get customer
        customer = None
        if data.get('customer_name'):
            customer, created = Customer.objects.get_or_create(
                phone=data.get('customer_phone', ''),
                defaults={
                    'name': data.get('customer_name', ''),
                    'address': data.get('customer_address', ''),
                    'doctor_name': data.get('doctor_name', ''),
                    'prescription_number': data.get('prescription_number', '')
                }
            )
        
        # Create bill
        bill = Bill.objects.create(
            customer=customer,
            customer_name=data.get('customer_name', 'Walk-in Customer'),
            customer_phone=data.get('customer_phone', ''),
            subtotal=Decimal(data.get('subtotal', 0)),
            discount_percentage=Decimal(data.get('discount_percentage', 0)),
            tax_percentage=Decimal(data.get('tax_percentage', 0)),
            payment_method=data.get('payment_method', 'cash'),
            amount_paid=Decimal(data.get('amount_paid', 0)),
            notes=data.get('notes', ''),
            created_by=request.user
        )
        
        # Create bill items
        for item_data in data['items']:
            medicine = Medicine.objects.get(id=item_data['medicine_id'])
            
            # Check stock availability
            if medicine.quantity < int(item_data['quantity']):
                bill.delete()  # Rollback
                return JsonResponse({
                    'success': False,
                    'message': f'Insufficient stock for {medicine.name}. Available: {medicine.quantity}'
                }, status=400)
            
            # Create bill item
            BillItem.objects.create(
                bill=bill,
                medicine=medicine,
                quantity=int(item_data['quantity']),
                unit_price=Decimal(item_data['unit_price'])
            )
        
        # Recalculate bill totals
        bill.calculate_totals()
        
        return JsonResponse({
            'success': True,
            'message': 'Bill created successfully',
            'bill_id': bill.id,
            'bill_number': bill.bill_number,
            'redirect_url': f'/bills/{bill.id}/'
        })
        
    except Medicine.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Medicine not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@login_required
def bill_list(request):
    """List all bills"""
    bills = Bill.objects.select_related('customer', 'created_by').prefetch_related('items')
    
    # Filters
    status = request.GET.get('status')
    payment_method = request.GET.get('payment_method')
    search = request.GET.get('search')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if status:
        bills = bills.filter(status=status)
    if payment_method:
        bills = bills.filter(payment_method=payment_method)
    if search:
        bills = bills.filter(
            Q(bill_number__icontains=search) |
            Q(customer_name__icontains=search) |
            Q(customer_phone__icontains=search)
        )
    if date_from:
        bills = bills.filter(created_at__date__gte=date_from)
    if date_to:
        bills = bills.filter(created_at__date__lte=date_to)
    
    # Statistics
    total_sales = bills.filter(status='completed').aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    
    total_bills = bills.count()
    
    context = {
        'bills': bills[:50],  # Paginate in production
        'total_sales': total_sales,
        'total_bills': total_bills,
    }
    
    return render(request, 'bill_list.html', context)


@login_required
def bill_detail(request, bill_id):
    """View bill details"""
    bill = get_object_or_404(
        Bill.objects.select_related('customer', 'created_by').prefetch_related('items__medicine'),
        id=bill_id
    )
    
    context = {
        'bill': bill,
    }
    
    return render(request, 'bill_detail.html', context)


@login_required
def print_bill(request, bill_id):
    """Print bill"""
    bill = get_object_or_404(
        Bill.objects.select_related('customer', 'created_by').prefetch_related('items__medicine'),
        id=bill_id
    )
    
    context = {
        'bill': bill,
    }
    
    return render(request, 'print_bill.html', context)


@login_required
@require_http_methods(["POST"])
def cancel_bill(request, bill_id):
    """Cancel a bill and restore stock"""
    try:
        bill = get_object_or_404(Bill, id=bill_id)
        
        if bill.status == 'cancelled':
            return JsonResponse({
                'success': False,
                'message': 'Bill is already cancelled'
            }, status=400)
        
        # Restore stock for all items
        for item in bill.items.all():
            item.medicine.quantity += item.quantity
            item.medicine.save()
            
            # Create reverse stock transaction
            StockTransaction.objects.create(
                medicine=item.medicine,
                transaction_type='return',
                quantity=item.quantity,
                price_per_unit=item.unit_price,
                total_amount=item.total_price,
                notes=f'Bill Cancelled: {bill.bill_number}',
                performed_by=request.user
            )
        
        # Update bill status
        bill.status = 'cancelled'
        bill.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Bill cancelled successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@login_required
def customer_list(request):
    """List all customers"""
    customers = Customer.objects.annotate(
        total_purchases=Count('bill')
    ).order_by('-created_at')
    
    search = request.GET.get('search')
    if search:
        customers = customers.filter(
            Q(name__icontains=search) |
            Q(phone__icontains=search) |
            Q(email__icontains=search)
        )
    
    context = {
        'customers': customers[:50],
    }
    
    return render(request, 'customer_list.html', context)


@login_required
def customer_detail(request, customer_id):
    """View customer details and purchase history"""
    customer = get_object_or_404(Customer, id=customer_id)
    bills = Bill.objects.filter(customer=customer).order_by('-created_at')
    
    total_spent = bills.filter(status='completed').aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    
    context = {
        'customer': customer,
        'bills': bills,
        'total_spent': total_spent,
    }
    
    return render(request, 'customer_detail.html', context)



# <----------old------------>

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Q
from .models import StaffProfile
import random
import string

def generate_employee_id():
    """Generate unique employee ID"""
    prefix = "EMP"
    random_num = ''.join(random.choices(string.digits, k=6))
    employee_id = f"{prefix}{random_num}"
    
    # Check if exists, regenerate if needed
    while StaffProfile.objects.filter(employee_id=employee_id).exists():
        random_num = ''.join(random.choices(string.digits, k=6))
        employee_id = f"{prefix}{random_num}"
    
    return employee_id

def generate_username(first_name, last_name):
    """Generate unique username from name"""
    base_username = f"{first_name.lower()}.{last_name.lower()}"
    username = base_username
    counter = 1
    
    while User.objects.filter(username=username).exists():
        username = f"{base_username}{counter}"
        counter += 1
    
    return username

def generate_password(length=10):
    """Generate random password"""
    characters = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(random.choice(characters) for i in range(length))
    return password

def send_credentials_email(user, password, staff_profile):
    """Send email with login credentials to new staff"""
    subject = 'MediCare Pharmacy - Your Account Credentials'
    
    message = f"""
    Dear {user.get_full_name()},

    Welcome to MediCare Pharmacy!

    Your account has been successfully created. Here are your login credentials:

    Employee ID: {staff_profile.employee_id}
    Username: {user.username}
    Password: {password}
    Email: {user.email}

    Role: {staff_profile.get_role_display()}
    Shift: {staff_profile.get_shift_display()}

    Please login to the system and change your password immediately for security purposes.

    Login URL: {settings.SITE_URL if hasattr(settings, 'SITE_URL') else 'http://localhost:8000'}

    If you have any questions, please contact the administrator.

    Best regards,
    MediCare Pharmacy Management
    """
    
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False

@login_required
def add_staff(request, pk=None):
    """Add or Edit Staff"""
    staff_profile = None
    if pk:
        staff_profile = get_object_or_404(StaffProfile, pk=pk)
    
    if request.method == 'POST':
        try:
            # Get form data
            first_name = request.POST.get('first_name')
            last_name = request.POST.get('last_name')
            email = request.POST.get('email')
            phone = request.POST.get('phone')
            
            if staff_profile:
                # Editing existing staff
                user = staff_profile.user
                user.first_name = first_name
                user.last_name = last_name
                user.email = email
                user.save()
                
                # Update staff profile
                staff_profile.phone = phone
                staff_profile.alternate_phone = request.POST.get('alternate_phone', '')
                staff_profile.address = request.POST.get('address')
                staff_profile.city = request.POST.get('city')
                staff_profile.state = request.POST.get('state')
                staff_profile.pincode = request.POST.get('pincode')
                staff_profile.role = request.POST.get('role')
                staff_profile.qualification = request.POST.get('qualification')
                staff_profile.experience_years = int(request.POST.get('experience_years', 0))
                staff_profile.license_number = request.POST.get('license_number', '')
                staff_profile.date_of_joining = request.POST.get('date_of_joining')
                staff_profile.shift = request.POST.get('shift')
                staff_profile.salary = float(request.POST.get('salary'))
                staff_profile.status = request.POST.get('status')
                staff_profile.emergency_contact_name = request.POST.get('emergency_contact_name')
                staff_profile.emergency_contact_phone = request.POST.get('emergency_contact_phone')
                staff_profile.emergency_contact_relation = request.POST.get('emergency_contact_relation')
                staff_profile.save()
                
                messages.success(request, f'Staff "{user.get_full_name()}" updated successfully!')
                
            else:
                # Creating new staff
                # Generate username and password
                username = generate_username(first_name, last_name)
                password = generate_password()
                employee_id = generate_employee_id()
                
                # Create user
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    is_staff=True,
                    is_active=True
                )
                
                # Create staff profile
                staff_profile = StaffProfile.objects.create(
                    user=user,
                    employee_id=employee_id,
                    phone=phone,
                    alternate_phone=request.POST.get('alternate_phone', ''),
                    address=request.POST.get('address'),
                    city=request.POST.get('city'),
                    state=request.POST.get('state'),
                    pincode=request.POST.get('pincode'),
                    role=request.POST.get('role'),
                    qualification=request.POST.get('qualification'),
                    experience_years=int(request.POST.get('experience_years', 0)),
                    license_number=request.POST.get('license_number', ''),
                    date_of_joining=request.POST.get('date_of_joining'),
                    shift=request.POST.get('shift'),
                    salary=float(request.POST.get('salary')),
                    status='active',
                    emergency_contact_name=request.POST.get('emergency_contact_name'),
                    emergency_contact_phone=request.POST.get('emergency_contact_phone'),
                    emergency_contact_relation=request.POST.get('emergency_contact_relation'),
                    created_by=request.user
                )
                
                # Send credentials via email
                email_sent = send_credentials_email(user, password, staff_profile)
                
                if email_sent:
                    messages.success(
                        request, 
                        f'Staff "{user.get_full_name()}" added successfully! Login credentials have been sent to {email}.'
                    )
                else:
                    messages.warning(
                        request,
                        f'Staff added but email could not be sent. Username: {username}, Password: {password}'
                    )
            
            return redirect('staff_list')
            
        except Exception as e:
            messages.error(request, f'Error {"updating" if pk else "adding"} staff: {str(e)}')
            if pk:
                staff_profile = get_object_or_404(StaffProfile, pk=pk)
    
    context = {
        'staff_profile': staff_profile,
        'is_edit': staff_profile is not None,
        'role_choices': StaffProfile.ROLE_CHOICES,
        'shift_choices': StaffProfile.SHIFT_CHOICES,
        'status_choices': StaffProfile.STATUS_CHOICES,
    }
    return render(request, 'add_staff.html', context)


@login_required
def staff_list(request):
    """List all staff members"""
    search_query = request.GET.get('search', '')
    role_filter = request.GET.get('role', '')
    status_filter = request.GET.get('status', '')
    
    # Base queryset
    staff_members = StaffProfile.objects.select_related('user').all()
    
    # Apply search
    if search_query:
        staff_members = staff_members.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__email__icontains=search_query) |
            Q(employee_id__icontains=search_query) |
            Q(phone__icontains=search_query)
        )
    
    # Apply role filter
    if role_filter:
        staff_members = staff_members.filter(role=role_filter)
    
    # Apply status filter
    if status_filter:
        staff_members = staff_members.filter(status=status_filter)
    
    # Calculate stats
    total_staff = StaffProfile.objects.count()
    active_staff = StaffProfile.objects.filter(status='active').count()
    on_leave = StaffProfile.objects.filter(status='on_leave').count()
    inactive_staff = StaffProfile.objects.filter(status='inactive').count()
    
    context = {
        'staff_members': staff_members,
        'search_query': search_query,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'role_choices': StaffProfile.ROLE_CHOICES,
        'status_choices': StaffProfile.STATUS_CHOICES,
        'total_staff': total_staff,
        'active_staff': active_staff,
        'on_leave': on_leave,
        'inactive_staff': inactive_staff,
    }
    return render(request, 'staff_list.html', context)


@login_required
def delete_staff(request, pk):
    """Delete staff member"""
    staff_profile = get_object_or_404(StaffProfile, pk=pk)
    
    if request.method == 'POST':
        name = staff_profile.user.get_full_name()
        user = staff_profile.user
        staff_profile.delete()
        user.delete()
        messages.success(request, f'Staff "{name}" deleted successfully!')
        return redirect('staff_list')
    
    return redirect('staff_list')