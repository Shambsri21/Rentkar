from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Vehicle, Booking, CustomUser, Manager
from django.utils import timezone
from allauth.account.forms import SignupForm, LoginForm
from django.contrib.auth import get_user_model, login, authenticate
from django.urls import reverse
from django.db import transaction
from django.core.exceptions import ValidationError

class CustomLoginForm(LoginForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['login'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Email'})
        self.fields['password'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Password'})

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('login')
        password = cleaned_data.get('password')

        if email and password:
            user = authenticate(username=email, password=password)
            if not user:
                raise ValidationError('Invalid email or password.')
            cleaned_data['user'] = user
        return cleaned_data

class CustomSignupForm(SignupForm):
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    phone_number = forms.CharField(max_length=15, required=True)
    address = forms.CharField(widget=forms.Textarea, required=True)
    role = forms.ChoiceField(choices=CustomUser.ROLE_CHOICES, required=True)
    license_id = forms.CharField(max_length=20, required=False)
    branch_name = forms.CharField(max_length=100, required=False)
    branch_location = forms.CharField(max_length=200, required=False)
    password1 = forms.CharField(widget=forms.PasswordInput, required=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})
        self.fields['email'].required = True
        self.fields['password1'].widget.attrs.update({
            'placeholder': 'Password',
            'autocomplete': 'new-password'
        })

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError("This email address is already registered. Please use a different email or try to log in.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        
        if role == 'manager':
            branch_name = cleaned_data.get('branch_name')
            branch_location = cleaned_data.get('branch_location')
            
            if not branch_name:
                self.add_error('branch_name', 'Branch name is required for managers')
            if not branch_location:
                self.add_error('branch_location', 'Branch location is required for managers')
        elif role == 'customer':
            license_id = cleaned_data.get('license_id')
            if not license_id:
                self.add_error('license_id', 'License ID is required for customers')
        
        # Make sure we have a password
        if not cleaned_data.get('password1'):
            self.add_error('password1', 'Password is required')
            
        return cleaned_data

    @transaction.atomic
    def save(self, request):
        try:
            # Create the user first
            user = super().save(request)
            
            # Set user attributes
            user.first_name = self.cleaned_data.get('first_name')
            user.last_name = self.cleaned_data.get('last_name')
            user.phone_number = self.cleaned_data.get('phone_number')
            user.address = self.cleaned_data.get('address')
            user.role = self.cleaned_data.get('role')
            
            if user.role == 'customer':
                user.license_id = self.cleaned_data.get('license_id')
            
            user.save()
            
            # Create manager profile if user is a manager
            if user.role == 'manager':
                manager = Manager.objects.create(
                    user=user,
                    branch_name=self.cleaned_data.get('branch_name'),
                    branch_location=self.cleaned_data.get('branch_location')
                )
                manager.save()
            
            # Ensure the user is logged in
            login(request, user)
            
            return user
            
        except Exception as e:
            # If anything goes wrong, add it as a form error
            self.add_error(None, f"Error creating account: {str(e)}")
            raise

class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ['name', 'model', 'vehicle_type', 'fuel_type', 'registration_number', 
                 'daily_rate', 'is_available', 'description', 'image']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
        labels = {
            'name': 'Vehicle Name',
            'model': 'Model Number',
            'vehicle_type': 'Vehicle Type',
            'fuel_type': 'Fuel Type',
            'registration_number': 'Vehicle Plate Number',
            'daily_rate': 'Daily Rental Rate (₹)',
            'is_available': 'Available for Rent',
            'description': 'Vehicle Description',
            'image': 'Vehicle Image'
        }
        help_texts = {
            'registration_number': 'Enter the vehicle\'s registration/plate number',
            'daily_rate': 'Enter the daily rental rate in rupees',
            'is_available': 'Uncheck if the vehicle is currently not available for rent',
        }

class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'min': timezone.now().date().isoformat()
            }),
            'end_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'min': timezone.now().date().isoformat()
            }),
        }
        labels = {
            'start_date': 'Pick-up Date',
            'end_date': 'Return Date',
        }
        help_texts = {
            'start_date': 'Select when you want to pick up the vehicle',
            'end_date': 'Select when you want to return the vehicle',
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date:
            if start_date < timezone.now().date():
                raise forms.ValidationError("Start date cannot be in the past")
            if end_date <= start_date:
                raise forms.ValidationError("End date must be after start date")
            if (end_date - start_date).days > 30:
                raise forms.ValidationError("Maximum booking duration is 30 days")

        return cleaned_data

class PaymentForm(forms.Form):
    card_number = forms.CharField(
        max_length=19,  # 16 digits + 3 spaces
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '1234 5678 9012 3456',
            'pattern': '[0-9]{4} [0-9]{4} [0-9]{4} [0-9]{4}',
            'inputmode': 'numeric',
            'title': 'Enter a valid 16-digit card number with spaces (e.g., 1234 5678 9012 3456)'
        })
    )
    expiry_date = forms.CharField(
        max_length=5,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'MM/YY',
            'pattern': '[0-9]{2}/[0-9]{2}',
            'title': 'Enter date in MM/YY format (e.g., 03/25)'
        })
    )
    cvv = forms.CharField(
        max_length=3,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '123',
            'pattern': '[0-9]{3}',
            'inputmode': 'numeric',
            'title': 'Enter 3-digit CVV number'
        })
    )

    def clean_card_number(self):
        card_number = self.cleaned_data.get('card_number')
        # Remove any spaces from the card number
        card_number = card_number.replace(' ', '')
        if not card_number.isdigit():
            raise forms.ValidationError("Card number must contain only digits")
        if len(card_number) != 16:
            raise forms.ValidationError("Card number must be 16 digits long")
        return ' '.join([card_number[i:i+4] for i in range(0, 16, 4)])  # Format with spaces

class ProfileForm(forms.ModelForm):
    branch_name = forms.CharField(max_length=100, required=False, label='Branch Name')

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'address']
        help_texts = {
            'first_name': 'Your first name',
            'last_name': 'Your last name',
            'phone_number': 'Your contact number',
            'address': 'Your current address',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        if instance:
            if instance.role == 'manager':
                try:
                    manager = instance.manager
                    self.fields['branch_name'].initial = manager.branch_name
                except:
                    pass
            elif instance.role == 'customer':
                self.fields['license_id'] = forms.CharField(
                    max_length=20,
                    required=True,
                    label='Driving License ID',
                    initial=instance.license_id
                )

    def save(self, commit=True):
        user = super().save(commit=False)
        if user.role == 'customer':
            user.license_id = self.cleaned_data.get('license_id')
        if commit:
            user.save()
            if user.role == 'manager':
                from .models import Manager
                manager, created = Manager.objects.get_or_create(user=user)
                manager.branch_name = self.cleaned_data.get('branch_name')
                manager.save()
        return user

class VehicleFilterForm(forms.Form):
    VEHICLE_TYPE_CHOICES = [('', 'All Types')] + Vehicle.VEHICLE_TYPE_CHOICES
    FUEL_TYPE_CHOICES = [('', 'All Fuel Types')] + Vehicle.FUEL_TYPE_CHOICES
    
    vehicle_type = forms.ChoiceField(
        choices=VEHICLE_TYPE_CHOICES, 
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    fuel_type = forms.ChoiceField(
        choices=FUEL_TYPE_CHOICES, 
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    min_price = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Min Price',
            'min': '0'
        })
    )
    max_price = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Max Price',
            'min': '0'
        })
    )
    sort_by = forms.ChoiceField(
        choices=[
            ('', 'Default'),
            ('price_asc', 'Price: Low to High'),
            ('price_desc', 'Price: High to Low'),
            ('name_asc', 'Name: A to Z'),
            ('name_desc', 'Name: Z to A')
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def clean(self):
        cleaned_data = super().clean()
        min_price = cleaned_data.get('min_price')
        max_price = cleaned_data.get('max_price')
        
        if min_price and max_price and min_price > max_price:
            raise forms.ValidationError("Minimum price cannot be greater than maximum price.")
        
        return cleaned_data 