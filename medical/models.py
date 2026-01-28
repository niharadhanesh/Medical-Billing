from django.core.validators import MinValueValidator
from django.db import models
# Create your models here.
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator



class Medicine(models.Model):
    CATEGORY_CHOICES = [
        ('tablet', 'Tablet'),
        ('capsule', 'Capsule'),
        ('syrup', 'Syrup'),
        ('injection', 'Injection'),
        ('ointment', 'Ointment'),
        ('drops', 'Drops'),
        ('inhaler', 'Inhaler'),
        ('other', 'Other'),
    ]
    
    name = models.CharField(max_length=200)
    generic_name = models.CharField(max_length=200, blank=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    manufacturer = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Stock details
    quantity = models.IntegerField(default=0)
    reorder_level = models.IntegerField(default=10)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Date information
    manufacturing_date = models.DateField()
    expiry_date = models.DateField()
    
    # Additional info
    batch_number = models.CharField(max_length=100)
    rack_number = models.CharField(max_length=50, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.name} ({self.generic_name})"
    
    @property
    def is_low_stock(self):
        return self.quantity <= self.reorder_level
    
    @property
    def is_expired(self):
        return self.expiry_date < timezone.now().date()
    
    @property
    def stock_status(self):
        if self.is_expired:
            return 'expired'
        elif self.quantity == 0:
            return 'out_of_stock'
        elif self.is_low_stock:
            return 'low_stock'
        return 'in_stock'


class StockTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('purchase', 'Purchase'),
        ('sale', 'Sale'),
        ('return', 'Return'),
        ('expired', 'Expired'),
        ('damaged', 'Damaged'),
    ]
    
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    quantity = models.IntegerField()
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    transaction_date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['-transaction_date']
        
    def __str__(self):
        return f"{self.transaction_type} - {self.medicine.name} ({self.quantity})"
    
    def save(self, *args, **kwargs):
        # Calculate total amount
        self.total_amount = self.quantity * self.price_per_unit
        
        # Only auto-update stock for actual transactions (not edit adjustments)
        # The view handles stock updates for edits
        # This prevents double-counting when editing medicines
        
        super().save(*args, **kwargs)
        
        

class Customer(models.Model):
    """Customer/Patient Information"""
    name = models.CharField(max_length=200, db_index=True)
    phone = models.CharField(max_length=20, db_index=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True)
    
    # Medical information
    doctor_name = models.CharField(max_length=200, blank=True, help_text="Prescribing doctor's name")
    prescription_number = models.CharField(max_length=100, blank=True, help_text="Prescription reference number")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['phone']),
            models.Index(fields=['name']),
        ]
        unique_together = [['phone', 'name']]  # Prevent duplicate customers
    
    def __str__(self):
        return f"{self.name} - {self.phone}"
    
    @property
    def total_purchases(self):
        """Get total number of purchases"""
        return self.bills.filter(status='completed').count()
    
    @property
    def total_spent(self):
        """Get total amount spent"""
        from django.db.models import Sum
        total = self.bills.filter(status='completed').aggregate(
            total=Sum('total_amount')
        )['total']
        return total or Decimal('0.00')
    
    @property
    def last_purchase_date(self):
        """Get date of last purchase"""
        last_bill = self.bills.filter(status='completed').order_by('-created_at').first()
        return last_bill.created_at if last_bill else None


# ============================================================================
# BILL MODEL
# ============================================================================
from django.core.validators import MinValueValidator

class Bill(models.Model):
    """Main billing/invoice record"""
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('upi', 'UPI'),
        ('cheque', 'Cheque'),
        ('credit', 'Credit'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]
    
    # Bill identification
    bill_number = models.CharField(max_length=50, unique=True, editable=False, db_index=True)
    
    # Customer information
    customer = models.ForeignKey(
        Customer, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='bills',
        help_text="Linked customer record (optional)"
    )
    customer_name = models.CharField(max_length=200, help_text="Customer name for this bill")
    customer_phone = models.CharField(max_length=20, blank=True, help_text="Customer phone for this bill")
    
    # Pricing details
    subtotal = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Total before discount and tax"
    )
    discount_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Discount percentage (0-100)"
    )
    discount_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Calculated discount amount"
    )
    tax_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Tax/GST percentage (0-100)"
    )
    tax_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Calculated tax amount"
    )
    total_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Final total amount"
    )
    
    # Payment information
    payment_method = models.CharField(
        max_length=20, 
        choices=PAYMENT_METHODS, 
        default='cash',
        db_index=True
    )
    amount_paid = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Amount received from customer"
    )
    amount_due = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text="Remaining amount (can be negative for change)"
    )
    
    # Bill status and notes
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='completed',
        db_index=True
    )
    notes = models.TextField(blank=True, help_text="Additional notes or comments")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='created_bills'
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['bill_number']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['payment_method', 'created_at']),
            models.Index(fields=['customer', 'created_at']),
        ]
        
    def __str__(self):
        return f"{self.bill_number} - {self.customer_name} - ₹{self.total_amount}"
    
    def save(self, *args, **kwargs):
        # Generate bill number if not exists
        if not self.bill_number:
            self.bill_number = self.generate_bill_number()
        
        # Calculate all amounts
        self.calculate_amounts()
        
        super().save(*args, **kwargs)
    
    def generate_bill_number(self):
        """Generate unique bill number: BILL-YYYYMMDD-XXXX"""
        from django.db.models import Max
        
        today = timezone.now().date()
        date_str = today.strftime('%Y%m%d')
        prefix = f'BILL-{date_str}'
        
        # Get last bill number for today
        last_bill = Bill.objects.filter(
            bill_number__startswith=prefix
        ).aggregate(Max('bill_number'))
        
        if last_bill['bill_number__max']:
            last_number = int(last_bill['bill_number__max'].split('-')[-1])
            new_number = last_number + 1
        else:
            new_number = 1
        
        return f'{prefix}-{new_number:04d}'
    
    def calculate_amounts(self):
        """Calculate discount, tax, and total amounts"""
        # Calculate discount amount
        self.discount_amount = (self.subtotal * self.discount_percentage) / 100
        
        # Amount after discount
        amount_after_discount = self.subtotal - self.discount_amount
        
        # Calculate tax amount
        self.tax_amount = (amount_after_discount * self.tax_percentage) / 100
        
        # Calculate total
        self.total_amount = amount_after_discount + self.tax_amount
        
        # Calculate amount due
        self.amount_due = self.total_amount - self.amount_paid
    
    def calculate_totals(self):
        """Recalculate subtotal from bill items"""
        items_total = sum(item.total_price for item in self.items.all())
        self.subtotal = items_total
        self.save()
    
    @property
    def total_items(self):
        """Get total number of items in bill"""
        return self.items.count()
    
    @property
    def total_quantity(self):
        """Get total quantity of all items"""
        from django.db.models import Sum
        total = self.items.aggregate(total=Sum('quantity'))['total']
        return total or 0
    
    @property
    def is_paid(self):
        """Check if bill is fully paid"""
        return self.amount_due <= 0
    
    @property
    def change_amount(self):
        """Get change amount if overpaid"""
        return abs(self.amount_due) if self.amount_due < 0 else 0


# ============================================================================
# BILL ITEM MODEL
# ============================================================================

class BillItem(models.Model):
    """Individual line items in a bill"""
    bill = models.ForeignKey(
        Bill, 
        on_delete=models.CASCADE, 
        related_name='items',
        help_text="Parent bill"
    )
    medicine = models.ForeignKey(
        Medicine, 
        on_delete=models.PROTECT,
        help_text="Medicine being sold (protected from deletion)"
    )
    
    # Store medicine details for historical record
    medicine_name = models.CharField(max_length=200, help_text="Medicine name at time of sale")
    batch_number = models.CharField(max_length=100, help_text="Batch number at time of sale")
    
    # Quantity and pricing
    quantity = models.IntegerField(validators=[MinValueValidator(1)], help_text="Quantity sold")
    unit_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Price per unit at time of sale"
    )
    total_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Total price for this item (quantity × unit_price)"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['id']
        indexes = [
            models.Index(fields=['bill', 'medicine']),
        ]
    
    def __str__(self):
        return f"{self.medicine_name} × {self.quantity} = ₹{self.total_price}"
    
    def save(self, *args, **kwargs):
        # Store medicine details at time of sale
        if self.medicine:
            self.medicine_name = self.medicine.name
            self.batch_number = self.medicine.batch_number
            
            # Use medicine's selling price if unit_price not provided
            if not self.unit_price:
                self.unit_price = self.medicine.selling_price
        
        # Calculate total price
        self.total_price = self.quantity * self.unit_price
        
        # Check if this is a new item (not being updated)
        is_new = self.pk is None
        
        super().save(*args, **kwargs)
        
        # Only update stock and create transaction for new items
        if is_new and self.medicine:
            # Update medicine stock
            self.medicine.quantity -= self.quantity
            self.medicine.save()
            
            # Create stock transaction
            StockTransaction.objects.create(
                medicine=self.medicine,
                transaction_type='sale',
                quantity=self.quantity,
                price_per_unit=self.unit_price,
                total_amount=self.total_price,
                notes=f'Bill: {self.bill.bill_number}',
                bill_reference=self.bill.bill_number,
                performed_by=self.bill.created_by
            )
    
    @property
    def profit(self):
        """Calculate profit for this item"""
        if self.medicine:
            return (self.unit_price - self.medicine.unit_price) * self.quantity
        return Decimal('0.00')


# ============================================================================
# ADDITIONAL MODELS (Optional but Recommended)
# ============================================================================

class PaymentTransaction(models.Model):
    """Track individual payment transactions for a bill"""
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='payments')
    payment_method = models.CharField(max_length=20, choices=Bill.PAYMENT_METHODS)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    transaction_reference = models.CharField(max_length=100, blank=True, help_text="Cheque number, UPI ID, etc.")
    payment_date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['-payment_date']
    
    def __str__(self):
        return f"{self.bill.bill_number} - {self.payment_method} - ₹{self.amount}"


class BillRefund(models.Model):
    """Track bill refunds"""
    original_bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='refunds')
    refund_bill = models.OneToOneField(Bill, on_delete=models.CASCADE, related_name='refund_for')
    reason = models.TextField(help_text="Reason for refund")
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    refund_date = models.DateTimeField(auto_now_add=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['-refund_date']
    
    def __str__(self):
        return f"Refund for {self.original_bill.bill_number} - ₹{self.refund_amount}"
    
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# Add this to your existing models.py

class StaffProfile(models.Model):
    ROLE_CHOICES = [
        ('pharmacist', 'Pharmacist'),
        ('cashier', 'Cashier'),
        ('inventory_manager', 'Inventory Manager'),
        ('assistant', 'Assistant'),
        ('other', 'Other'),
    ]
    
    SHIFT_CHOICES = [
        ('morning', 'Morning (6 AM - 2 PM)'),
        ('afternoon', 'Afternoon (2 PM - 10 PM)'),
        ('night', 'Night (10 PM - 6 AM)'),
        ('full_time', 'Full Time (9 AM - 6 PM)'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('on_leave', 'On Leave'),
        ('terminated', 'Terminated'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff_profile')
    
    # Personal Information
    employee_id = models.CharField(max_length=20, unique=True)
    phone = models.CharField(max_length=15)
    alternate_phone = models.CharField(max_length=15, blank=True)
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    
    # Professional Information
    role = models.CharField(max_length=50, choices=ROLE_CHOICES)
    qualification = models.CharField(max_length=200)
    experience_years = models.IntegerField(default=0)
    license_number = models.CharField(max_length=100, blank=True)
    
    # Employment Details
    date_of_joining = models.DateField()
    shift = models.CharField(max_length=20, choices=SHIFT_CHOICES)
    salary = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Emergency Contact
    emergency_contact_name = models.CharField(max_length=200)
    emergency_contact_phone = models.CharField(max_length=15)
    emergency_contact_relation = models.CharField(max_length=50)
    
    # Documents
    photo = models.ImageField(upload_to='staff_photos/', blank=True, null=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_staff')
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.employee_id}"
    
    @property
    def full_name(self):
        return self.user.get_full_name()
    
    @property
    def is_active_staff(self):
        return self.status == 'active' and self.user.is_active


class StaffAttendance(models.Model):
    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField(default=timezone.now)
    check_in = models.TimeField(null=True, blank=True)
    check_out = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('half_day', 'Half Day'),
        ('leave', 'Leave'),
    ], default='absent')
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-date']
        unique_together = ['staff', 'date']
        
    def __str__(self):
        return f"{self.staff.user.get_full_name()} - {self.date} - {self.status}"