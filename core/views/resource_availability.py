from django.shortcuts import get_object_or_404, render
from core.models import *
from core.forms import UserProfileForm
from core.views.unsorted import date_range_to_list
from django.http import HttpResponseNotAllowed


def CheckRoomAvailability(request, location_slug):
    if not request.method == 'POST':
        return HttpResponseNotAllowed('Only POST requests supported')

    location = get_object_or_404(Location, slug=location_slug)
    arrive_str = request.POST.get('arrive')
    depart_str = request.POST.get('depart')
    a_month, a_day, a_year = arrive_str.split("/")
    d_month, d_day, d_year = depart_str.split("/")
    arrive = datetime.date(int(a_year), int(a_month), int(a_day))
    depart = datetime.date(int(d_year), int(d_month), int(d_day))
    capacity = location.capacity(arrive, depart)
    date_list = date_range_to_list(arrive, depart)
    available_bookings = {}
    free_rooms = location.rooms_free(arrive, depart)
    for room in free_rooms:
        # Create some mock bookings for each available room so we can generate
        # the bill. These are NOT saved.
        mock_use = Use(id=-1, resource=room, arrive=arrive, depart=depart, location=location)
        mock_booking = Booking(id=-1, use=mock_use)
        bill_line_items = mock_booking.generate_bill(delete_old_items=False, save=False)
        total = Decimal(0.0)
        for item in bill_line_items:
            if not item.paid_by_house:
                total = Decimal(total) + Decimal(item.amount)
        nights = mock_booking.use.total_nights()
        available_bookings[room] = {'bill_line_items': bill_line_items, 'nights': nights, 'total': total}

    new_profile_form = UserProfileForm()
    if request.user.is_authenticated():
        current_user = request.user
    else:
        current_user = None

    # base previous and next on the arrival date. note that these dates will
    # also have a day associated with them but we don't use that.
    prev_month = arrive - relativedelta(months=1)
    next_month = arrive + relativedelta(months=1)

    all_users = User.objects.all().order_by('username')
    return render(
        request,
        "snippets/availability_calendar.html",
        {
            'availability_table': capacity,
            'dates': date_list,
            'current_user': current_user,
            'available_bookings': available_bookings,
            'arrive_date': arrive_str,
            'depart_date': depart_str,
            'arrive': arrive,
            'depart': depart,
            'new_profile_form': new_profile_form,
            'all_users': all_users,
            'prev_month': prev_month,
            'next_month': next_month
        }
    )
