from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta
from django.db.models.signals import post_save
from django.dispatch import receiver

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'manager')
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)

class CustomUser(AbstractUser):
    username = None  # Remove username field
    ROLE_CHOICES = [
        ('customer', 'Customer'),
        ('manager', 'Manager'),
    ]
    
    email = models.EmailField(_('email address'), unique=True)
    phone_number = models.CharField(max_length=15)
    address = models.TextField()
    license_id = models.CharField(max_length=20, blank=True, null=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='customer')
    email_verified = models.BooleanField(default=False)
    
    objects = CustomUserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'phone_number', 'address', 'role']
    
    def __str__(self):
        return f"{self.email} ({self.get_role_display()})"
    
    def is_manager(self):
        return self.role == 'manager'
    
    def is_customer(self):
        return self.role == 'customer'

class Manager(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, primary_key=True)
    branch_name = models.CharField(max_length=100)
    branch_location = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.branch_name}"

@receiver(post_save, sender=CustomUser)
def create_manager_profile(sender, instance, created, **kwargs):
    if created and instance.role == 'manager':
        # Create a default Manager profile for new manager users
        Manager.objects.create(
            user=instance,
            branch_name=f"{instance.get_full_name()}'s Branch",
            branch_location="Default Location"
        )

class Vehicle(models.Model):
    VEHICLE_TYPE_CHOICES = [
        ('2W', 'Two Wheeler'),
        ('4W', 'Four Wheeler'),
    ]

    FUEL_TYPE_CHOICES = [
        ('EV', 'Electric'),
        ('PETROL', 'Petrol'),
        ('DIESEL', 'Diesel'),
    ]

    vehicle_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    vehicle_type = models.CharField(max_length=2, choices=VEHICLE_TYPE_CHOICES)
    fuel_type = models.CharField(max_length=10, choices=FUEL_TYPE_CHOICES)
    registration_number = models.CharField(max_length=20, unique=True)
    daily_rate = models.DecimalField(max_digits=10, decimal_places=2)
    is_available = models.BooleanField(default=True)
    image = models.ImageField(upload_to='vehicle_images/', blank=True, null=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    branch = models.ForeignKey('Manager', on_delete=models.CASCADE, related_name='vehicles')

    def __str__(self):
        return f"{self.name} - {self.model} ({self.registration_number})"

class Booking(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('CANCELLED', 'Cancelled'),
        ('COMPLETED', 'Completed'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PAID', 'Paid'),
        ('FAILED', 'Failed'),
        ('REFUNDED', 'Refunded'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('CREDIT_CARD', 'Credit Card'),
        ('DEBIT_CARD', 'Debit Card'),
    ]
    
    booking_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    total_cost = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='PENDING')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, null=True, blank=True)
    transaction_id = models.CharField(max_length=100, null=True, blank=True)
    card_last_four = models.CharField(max_length=4, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Booking {self.booking_id} - {self.vehicle.name}"

    def clean(self):
        if self.start_date is None or self.end_date is None:
            raise ValidationError("Both start date and end date are required")
            
        if self.end_date <= self.start_date:
            raise ValidationError("End date must be after start date")
        
        # Only check for overlapping bookings if vehicle is set
        if hasattr(self, 'vehicle') and self.vehicle is not None:
            overlapping_bookings = Booking.objects.filter(
                vehicle=self.vehicle,
                status__in=['CONFIRMED', 'PENDING'],
                start_date__lte=self.end_date,
                end_date__gte=self.start_date
            ).exclude(booking_id=self.booking_id)
            
            if overlapping_bookings.exists():
                raise ValidationError("This vehicle is already booked for the selected dates")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

class Rental(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    vehicle = models.ForeignKey('Vehicle', on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_cost = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.vehicle.name} ({self.status})"
