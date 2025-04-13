from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import Vehicle, Booking, CustomUser, Manager, Rental
from .forms import VehicleForm, BookingForm, ProfileForm, VehicleFilterForm, PaymentForm, CustomSignupForm
from datetime import datetime, timedelta
from django.contrib.auth import authenticate, login
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy, reverse
from allauth.account.views import SignupView
import time

class CustomSignupView(SignupView):
    template_name = 'account/signup.html'
    form_class = CustomSignupForm

    def form_valid(self, form):
        try:
            # First try to save the user
            user = form.save(self.request)
            
            # Add success message
            messages.success(self.request, 'Account created successfully!')
            
            # Determine redirect URL based on role
            if user.role == 'manager':
                return redirect('manager_dashboard')
            return redirect('home')
            
        except Exception as e:
            # Log the error for debugging
            print(f"Error in signup: {str(e)}")
            
            # Add error message
            messages.error(self.request, f'Error creating account: {str(e)}')
            return self.form_invalid(form)

    def form_invalid(self, form):
        # Add form errors to messages
        for field, errors in form.errors.items():
            for error in errors:
                if field == '__all__':
                    messages.error(self.request, error)
                else:
                    messages.error(self.request, f"{field}: {error}")
        
        # Call parent's form_invalid
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add any messages to the context
        if hasattr(self.request, '_messages'):
            context['messages'] = messages.get_messages(self.request)
        return context

class CustomLoginView(LoginView):
    template_name = 'account/login.html'
    
    def form_valid(self, form):
        email = form.cleaned_data.get('login')  # allauth uses 'login' for the email field
        password = form.cleaned_data.get('password')
        
        # Authenticate using email
        user = authenticate(self.request, username=email, password=password)
        
        if user is not None:
            login(self.request, user)
            messages.success(self.request, f'Welcome back, {user.get_full_name()}!')
            
            # Redirect based on user role
            if user.role == 'manager':
                return redirect('manager_dashboard')
            return redirect('home')
        else:
            messages.error(self.request, 'Invalid email or password.')
            return self.form_invalid(form)

    def get_success_url(self):
        if self.request.user.role == 'manager':
            return reverse_lazy('manager_dashboard')
        return reverse_lazy('home')

def is_manager(user):
    """
    Check if the user is a manager by verifying:
    1. User is authenticated
    2. User's role is 'manager'
    3. User has an associated Manager profile
    """
    if not user.is_authenticated:
        return False
    if user.role != 'manager':
        return False
    try:
        return hasattr(user, 'manager') and user.manager is not None
    except Manager.DoesNotExist:
        return False

def is_customer(user):
    """Check if the user is a customer"""
    return user.is_authenticated and user.role == 'customer'

@login_required
def home(request):
    # Get featured EVs (electric vehicles)
    ev_vehicles = Vehicle.objects.filter(fuel_type='electric', is_available=True)[:3]
    
    # Get other featured vehicles (non-EV)
    featured_vehicles = Vehicle.objects.exclude(fuel_type='electric').filter(is_available=True)[:3]
    
    # Get total vehicle counts (only available ones)
    total_vehicles = Vehicle.objects.filter(is_available=True).count()
    ev_count = Vehicle.objects.filter(fuel_type='electric', is_available=True).count()
    
    context = {
        'ev_vehicles': ev_vehicles,
        'featured_vehicles': featured_vehicles,
        'total_vehicles': total_vehicles,
        'ev_count': ev_count,
    }
    
    return render(request, 'rental/home.html', context)

def vehicle_list(request):
    # Get only available vehicles by default
    vehicles = Vehicle.objects.filter(is_available=True)
    
    # Initialize filter form
    filter_form = VehicleFilterForm(request.GET)
    
    # Apply filters
    if filter_form.is_valid():
        # Vehicle type filter
        vehicle_type = filter_form.cleaned_data.get('vehicle_type')
        if vehicle_type:
            vehicles = vehicles.filter(vehicle_type=vehicle_type)
        
        # Fuel type filter
        fuel_type = filter_form.cleaned_data.get('fuel_type')
        if fuel_type:
            vehicles = vehicles.filter(fuel_type=fuel_type)
        
        # Price range filter
        min_price = filter_form.cleaned_data.get('min_price')
        max_price = filter_form.cleaned_data.get('max_price')
        if min_price:
            vehicles = vehicles.filter(daily_rate__gte=min_price)
        if max_price:
            vehicles = vehicles.filter(daily_rate__lte=max_price)
        
        # Sorting
        sort_by = filter_form.cleaned_data.get('sort_by')
        if sort_by:
            if sort_by == 'price_asc':
                vehicles = vehicles.order_by('daily_rate')
            elif sort_by == 'price_desc':
                vehicles = vehicles.order_by('-daily_rate')
            elif sort_by == 'name_asc':
                vehicles = vehicles.order_by('name')
            elif sort_by == 'name_desc':
                vehicles = vehicles.order_by('-name')
    else:
        # If form is not valid, show all available vehicles
        messages.warning(request, 'Invalid filter parameters. Showing all available vehicles.')
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(vehicles, 9)  # Show 9 vehicles per page
    
    try:
        vehicles = paginator.page(page)
    except PageNotAnInteger:
        vehicles = paginator.page(1)
    except EmptyPage:
        vehicles = paginator.page(paginator.num_pages)
    
    # Get filter parameters for pagination
    filter_params = request.GET.copy()
    if 'page' in filter_params:
        del filter_params['page']
    
    context = {
        'vehicles': vehicles,
        'filter_form': filter_form,
        'filter_params': filter_params.urlencode(),
    }
    
    return render(request, 'rental/vehicle_list.html', context)

def vehicle_detail(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle, pk=vehicle_id)
    return render(request, 'rental/vehicle_detail.html', {'vehicle': vehicle})

@login_required
def book_vehicle(request, vehicle_id):
    # Check if user is a customer
    if not is_customer(request.user):
        messages.error(request, 'Only customers can book vehicles.')
        return redirect('vehicle_detail', vehicle_id=vehicle_id)

    vehicle = get_object_or_404(Vehicle, pk=vehicle_id)
    if not vehicle.is_available:
        messages.error(request, 'Sorry, this vehicle is not available for booking.')
        return redirect('vehicle_detail', vehicle_id=vehicle_id)

    if request.method == 'POST':
        booking_form = BookingForm(request.POST)
        payment_form = PaymentForm(request.POST)
        
        if booking_form.is_valid() and payment_form.is_valid():
            try:
                with transaction.atomic():
                    # Create booking instance
                    booking = Booking(
                        user=request.user,
                        vehicle=vehicle,
                        start_date=booking_form.cleaned_data['start_date'],
                        end_date=booking_form.cleaned_data['end_date']
                    )
                    
                    # Calculate total cost
                    days = (booking.end_date - booking.start_date).days + 1
                    booking.total_cost = vehicle.daily_rate * days
                    
                    # Process payment
                    card_number = payment_form.cleaned_data['card_number'].replace(' ', '')
                    expiry_date = payment_form.cleaned_data['expiry_date']
                    cvv = payment_form.cleaned_data['cvv']
                    
                    # In a real application, you would integrate with a payment gateway here
                    # For development, we'll simulate a successful payment
                    booking.payment_status = 'PAID'
                    booking.status = 'CONFIRMED'
                    booking.payment_method = 'CREDIT_CARD'
                    booking.transaction_id = f"TXN{int(time.time())}"
                    booking.card_last_four = card_number[-4:]
                    
                    booking.clean()
                    booking.save()

                    rental = Rental.objects.create(
                        user=booking.user,
                        vehicle=vehicle,
                        start_date=booking.start_date,
                        end_date=booking.end_date,
                        status='active',
                        total_cost=booking.total_cost
                    )
                    
                    # Update vehicle availability
                    vehicle.is_available = False
                    vehicle.save()
                    
                    messages.success(request, f'Booking confirmed successfully! Transaction ID: {booking.transaction_id}')
                    return redirect('my_bookings')
                    
            except ValidationError as e:
                for error in e.messages:
                    messages.error(request, error)
            except Exception as e:
                messages.error(request, f'An error occurred while processing your booking: {str(e)}')
        else:
            # Collect all form errors
            if booking_form.errors:
                for field, errors in booking_form.errors.items():
                    if field == '__all__':
                        for error in errors:
                            messages.error(request, error)
                    else:
                        for error in errors:
                            messages.error(request, f"{booking_form.fields[field].label}: {error}")
            
            if payment_form.errors:
                for field, errors in payment_form.errors.items():
                    if field == '__all__':
                        for error in errors:
                            messages.error(request, error)
                    else:
                        for error in errors:
                            messages.error(request, f"{payment_form.fields[field].label}: {error}")
    else:
        initial_data = {
            'start_date': timezone.now().date(),
            'end_date': timezone.now().date() + timedelta(days=1)
        }
        booking_form = BookingForm(initial=initial_data)
        payment_form = PaymentForm()
    
    return render(request, 'rental/book_vehicle.html', {
        'booking_form': booking_form,
        'payment_form': payment_form,
        'vehicle': vehicle,
        'daily_rate': vehicle.daily_rate
    })

@login_required
def cancel_booking(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id, user=request.user)
    if request.method == 'POST':
        # If the booking had payment and the vehicle was marked unavailable, make it available again
        if booking.payment_status == 'paid' and not booking.vehicle.is_available:
            booking.vehicle.is_available = True
            booking.vehicle.save()
        
        booking.status = 'cancelled'
        booking.save()
        messages.success(request, 'Booking cancelled successfully!')
    return redirect('my_bookings')

@login_required
def my_bookings(request):
    # Get bookings for the current user only
    bookings = Booking.objects.filter(user=request.user).select_related('vehicle').order_by('-booking_id')
    
    # Get active rentals for the current user only
    active_rentals = Rental.objects.filter(user=request.user, status='active').select_related('vehicle')
    
    return render(request, 'rental/my_bookings.html', {
        'bookings': bookings,
        'active_rentals': active_rentals
    })

@login_required
@user_passes_test(is_manager)
def manager_dashboard(request):
    # Get the manager's branch
    manager = get_object_or_404(Manager, user=request.user)
    
    # Get statistics and data for the manager dashboard
    total_vehicles = Vehicle.objects.filter(branch=manager).count()
    active_rentals = Rental.objects.filter(vehicle__branch=manager, status='active').count()
    pending_requests = Rental.objects.filter(vehicle__branch=manager, status='pending').count()
    total_customers = CustomUser.objects.filter(role='customer').count()

    # Get recent rentals with more details for the manager's branch
    recent_rentals = Rental.objects.filter(vehicle__branch=manager).select_related('user', 'vehicle').order_by('-created_at')[:5]

    context = {
        'total_vehicles': total_vehicles,
        'active_rentals': active_rentals,
        'pending_requests': pending_requests,
        'total_customers': total_customers,
        'recent_rentals': recent_rentals,
    }
    
    return render(request, 'rental/manager_dashboard.html', context)

@login_required
@user_passes_test(is_manager)
def manage_vehicles(request):
    manager = get_object_or_404(Manager, user=request.user)
    vehicles = Vehicle.objects.filter(branch=manager).order_by('-vehicle_id')
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(vehicles, 10)  # Show 10 vehicles per page
    
    try:
        vehicles = paginator.page(page)
    except PageNotAnInteger:
        vehicles = paginator.page(1)
    except EmptyPage:
        vehicles = paginator.page(paginator.num_pages)
    
    return render(request, 'rental/manage_vehicles.html', {
        'vehicles': vehicles,
        'branch_name': manager.branch_name
    })

@login_required
@user_passes_test(is_manager)
def add_vehicle(request):
    if request.method == 'POST':
        form = VehicleForm(request.POST, request.FILES)
        if form.is_valid():
            # Get or create Manager profile for the user
            manager, created = Manager.objects.get_or_create(user=request.user)
            if created:
                messages.info(request, 'Manager profile created successfully!')
            
            vehicle = form.save(commit=False)
            vehicle.branch = manager
            vehicle.save()
            messages.success(request, 'Vehicle added successfully!')
            return redirect('manage_vehicles')
    else:
        form = VehicleForm()
    return render(request, 'rental/vehicle_form.html', {'form': form})

@login_required
@user_passes_test(is_manager)
def edit_vehicle(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle, pk=vehicle_id)
    if request.method == 'POST':
        form = VehicleForm(request.POST, request.FILES, instance=vehicle)
        if form.is_valid():
            form.save()
            messages.success(request, 'Vehicle updated successfully!')
            return redirect('manage_vehicles')
    else:
        form = VehicleForm(instance=vehicle)
    return render(request, 'rental/vehicle_form.html', {'form': form, 'vehicle': vehicle})

@login_required
@user_passes_test(is_manager)
def delete_vehicle(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle, pk=vehicle_id)
    if request.method == 'POST':
        vehicle.delete()
        messages.success(request, 'Vehicle deleted successfully!')
    return redirect('manage_vehicles')

@login_required
@user_passes_test(is_manager)
def manager_bookings(request):
    manager = get_object_or_404(Manager, user=request.user)
    bookings = Booking.objects.filter(vehicle__branch=manager)
    return render(request, 'rental/manager/bookings.html', {'bookings': bookings})

@login_required
def profile(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('profile')
    else:
        form = ProfileForm(instance=request.user)
    
    return render(request, 'rental/profile.html', {'form': form})

def manager_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        # Try to authenticate the manager
        user = authenticate(request, username=email, password=password)
        
        if user is not None and user.role == 'manager':
            # Ensure manager has a Manager profile
            try:
                manager = Manager.objects.get(user=user)
            except Manager.DoesNotExist:
                # Create a default Manager profile if it doesn't exist
                manager = Manager.objects.create(
                    user=user,
                    branch_name=f"{user.get_full_name()}'s Branch",
                    branch_location="Default Location"
                )
            
            login(request, user)
            messages.success(request, f'Welcome back, {user.get_full_name()}!')
            return redirect('manager_dashboard')
        else:
            if user is None:
                messages.error(request, 'Invalid email or password.')
            elif user.role != 'manager':
                messages.error(request, 'This account does not have manager privileges.')
            return redirect('account_login')
            
    return redirect('account_login')

@login_required
@user_passes_test(is_manager)
def manage_bookings(request):
    # Get the manager's branch
    manager = get_object_or_404(Manager, user=request.user)
    
    # Get all bookings for this manager's branch ordered by creation date
    bookings = Booking.objects.filter(vehicle__branch=manager).select_related('user', 'vehicle').order_by('-created_at')
    
    # Filter by status if provided
    status = request.GET.get('status')
    if status and status != 'all':
        bookings = bookings.filter(status=status.upper())  # Convert to uppercase to match Booking model's status choices
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(bookings, 10)  # Show 10 bookings per page
    
    try:
        bookings = paginator.page(page)
    except PageNotAnInteger:
        bookings = paginator.page(1)
    except EmptyPage:
        bookings = paginator.page(paginator.num_pages)
    
    return render(request, 'rental/manage_bookings.html', {
        'rentals': bookings,  # Keep the template variable name as 'rentals' to avoid template changes
        'status': status or 'all'
    })

@login_required
@user_passes_test(is_manager)
def manage_users(request):
    users = CustomUser.objects.filter(role='customer')
    return render(request, 'rental/manage_users.html', {'users': users})

@login_required
@user_passes_test(is_manager)
def approve_booking(request, booking_id):
    if request.method == 'POST':
        booking = get_object_or_404(Booking, booking_id=booking_id)
        if booking.status == 'PENDING':
            booking.status = 'CONFIRMED'
            booking.save()
            messages.success(request, 'Booking approved successfully!')
    return redirect('manage_bookings')

@login_required
@user_passes_test(is_manager)
def reject_booking(request, booking_id):
    if request.method == 'POST':
        booking = get_object_or_404(Booking, booking_id=booking_id)
        if booking.status == 'PENDING':
            booking.status = 'CANCELLED'
            booking.vehicle.is_available = True
            booking.vehicle.save()
            booking.save()
            messages.success(request, 'Booking rejected successfully!')
    return redirect('manage_bookings')

@login_required
@user_passes_test(is_manager)
def complete_booking(request, booking_id):
    if request.method == 'POST':
        booking = get_object_or_404(Booking, booking_id=booking_id)
        if booking.status == 'CONFIRMED':
            booking.status = 'COMPLETED'
            booking.vehicle.is_available = True
            booking.vehicle.save()
            booking.save()
            messages.success(request, 'Booking marked as completed successfully!')
    return redirect('manage_bookings')

@login_required
@user_passes_test(is_manager)
def activate_user(request, user_id):
    if request.method == 'POST':
        user = get_object_or_404(CustomUser, id=user_id)
        user.is_active = True
        user.save()
        messages.success(request, f'User {user.get_full_name()} has been activated.')
    return redirect('manage_users')

@login_required
@user_passes_test(is_manager)
def deactivate_user(request, user_id):
    if request.method == 'POST':
        user = get_object_or_404(CustomUser, id=user_id)
        if user.is_manager:
            messages.error(request, 'Cannot deactivate a manager account.')
        else:
            user.is_active = False
            user.save()
            messages.success(request, f'User {user.get_full_name()} has been deactivated.')
    return redirect('manage_users')

@login_required
@user_passes_test(is_manager)
def edit_user(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, f'User {user.get_full_name()} has been updated successfully!')
            return redirect('manage_users')
    else:
        form = ProfileForm(instance=user)
    return render(request, 'rental/manager/edit_user.html', {'form': form, 'user_obj': user})

@login_required
@user_passes_test(is_manager)
def delete_user(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)
    if request.method == 'POST':
        if user.is_manager:
            messages.error(request, 'Cannot delete a manager account.')
        else:
            user_name = user.get_full_name()
            user.delete()
            messages.success(request, f'User {user_name} has been deleted successfully!')
    return redirect('manage_users')
