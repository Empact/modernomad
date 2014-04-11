from celery.task.schedules import crontab
from celery.task import periodic_task
from core.models import Reservation, UserProfile
from django.contrib.auth.models import User
import datetime, json
from django.conf import settings
from django.contrib.sites.models import Site
from django.template.loader import get_template
from django.template import Context
from django.core import urlresolvers
from django.core.mail import EmailMultiAlternatives
import requests
from gather.tasks import published_events_today_local, events_pending

weekday_number_to_name = {
	0: "Monday",
	1: "Tuesday",
	2: "Wednesday",
	3: "Thursday",
	4: "Friday",
	5: "Saturday",
	6: "Sunday"
}


#@periodic_task(run_every=crontab(hour=22, minute=53, day_of_week="*"))  
#def test():      
#    print "HELLO WORLD"                    

@periodic_task(run_every=crontab(hour=5, minute=30))
def guest_today_notification():
	today = datetime.date.today()
	reservations_today = Reservation.today.confirmed()
	guest_emails = []
	for r in reservations_today:
		guest_emails.append(r.user.email)
	
	arriving_today = Reservation.objects.filter(arrive=today).filter(status='confirmed')
	departing_today = Reservation.objects.filter(depart=today).filter(status='confirmed')
	domain = Site.objects.get_current().domain
	events_today = published_events_today_local()

	plaintext = get_template('emails/guest_today_notification.txt')
	c = Context({
		'arriving' : arriving_today,
		'departing' : departing_today,
		'domain': domain,
		'events_today': events_today,
		'location_name': settings.LOCATION_NAME
	})
	text_content = plaintext.render(c)
	subject = settings.EMAIL_SUBJECT_PREFIX + "Events, Arrivals and Departures for %s" % (str(today))
	sender = settings.DEFAULT_FROM_EMAIL
	for guest_email in guest_emails:
		resp = requests.post("https://api.mailgun.net/v2/%s/messages" % settings.LIST_DOMAIN,
			auth=("api", settings.MAILGUN_API_KEY),
			data={
				"from": sender,
				"to": guest_email,
				"subject": subject,
				"text": text_content,
			}
		)

		print resp.text


@periodic_task(run_every=crontab(hour=4, minute=30))
#@periodic_task(run_every=crontab(minute="*")) # <-- for testing
def admin_today_notification():
	today = datetime.datetime.today() 
	arriving_today = Reservation.objects.filter(arrive=today).filter(status='confirmed')
	departing_today = Reservation.objects.filter(depart=today).filter(status='confirmed')
	domain = Site.objects.get_current().domain
	events_today = published_events_today_local()
	pending_or_feedback = events_pending()
	plaintext = get_template('emails/admin_today_notification.txt')
	c = Context({
		'arriving' : arriving_today,
		'departing' : departing_today,
		'domain': domain,
		'events_today': events_today,
		'events_pending': pending_or_feedback['pending'],
		'events_feedback': pending_or_feedback['feedback'],
	})
	text_content = plaintext.render(c)
	subject = settings.EMAIL_SUBJECT_PREFIX + "%s Events and Guests" % (str(today))
	sender = settings.DEFAULT_FROM_EMAIL
	house_admins = User.objects.filter(groups__name='house_admin')
	recipients = []
	for admin in house_admins:
		recipients.append(admin.email)
	msg = EmailMultiAlternatives(subject, text_content, sender, recipients)
	msg.send()

@periodic_task(run_every=crontab(hour=2, minute=0))
#@periodic_task(run_every=crontab(minute="*")) # <-- for testing
def guest_welcome():
	# get all reservations WELCOME_EMAIL_DAYS_AHEAD from now. 
	soon = datetime.datetime.today() + datetime.timedelta(days=settings.WELCOME_EMAIL_DAYS_AHEAD)
	upcoming = Reservation.objects.filter(arrive=soon).filter(status='confirmed')
	send_guest_welcome(upcoming)

def send_guest_welcome(upcoming):
	''' does the work of sending a guest welcome email, whether by scheduled
	task or manually for imminent reservations.'''
	# 'upcoming' needs to be a queryset
	domain = Site.objects.get_current().domain
	plaintext = get_template('emails/pre_arrival_welcome.txt')
	for reservation in upcoming:
		day_of_week = weekday_number_to_name[reservation.arrive.weekday()]
		c = Context({
			'first_name': reservation.user.first_name,
			'day_of_week' : day_of_week,
			'site_url': domain,
			'house_code': settings.HOUSE_ACCESS_CODE,
			'location_name': settings.LOCATION_NAME,
			'address': settings.LOCATION_ADDRESS,
			'ssid': settings.SSID,
			'ssid_password': settings.SSID_PASSWORD,
			'events_url' : domain + '/events/upcoming/',
			'current_email' : 'current@' + settings.LIST_DOMAIN,
			'profile_url' : "https://" + domain + urlresolvers.reverse('user_detail', args=(reservation.user.username,)),
			'reservation_url' : "https://" + domain + urlresolvers.reverse('reservation_detail', args=(reservation.location.slug, reservation.id,)),
		})
		text_content = plaintext.render(c)
		subject = "[Embassy SF] See you on %s" % day_of_week
		sender = settings.DEFAULT_FROM_EMAIL
		recipients = [reservation.user.email,]
		msg = EmailMultiAlternatives(subject, text_content, sender, recipients)
		msg.send()

@periodic_task(run_every=crontab(hour=0, minute=03))
def update_mailinglist_members():

	mailgun_api_key = settings.MAILGUN_API_KEY
	list_domain = settings.LIST_DOMAIN
	guest_list = "guests@" + list_domain
	current_list = "current@" + list_domain

	# current guests mailing list - delete and recrete to set membership
	resp = requests.delete("https://api.mailgun.net/v2/lists/%s" % guest_list, auth=('api', mailgun_api_key))
	print resp.text
	resp = requests.post("https://api.mailgun.net/v2/lists", auth=('api', mailgun_api_key), data={"address": guest_list, "name": "Current Guests", "access_level": "members"})
	print resp.text

	today = datetime.date.today()
	reservations_today = Reservation.today.confirmed()
	guest_emails = []
	for r in reservations_today:
		guest_emails.append(r.user.email)
	resp= requests.post("https://api.mailgun.net/v2/lists/%s/members.json" % guest_list, 
			data= {
				"members":json.dumps(guest_emails), 
				"subscribed": True
				}, 
				auth=('api', mailgun_api_key)
			)
	print "subscribe call responded with:"
	print resp.text
	resp = requests.get( "https://api.mailgun.net/v2/lists/%s/members" % guest_list,
					        auth=('api', mailgun_api_key))
	print resp.text

	# current guests and residents mailing list- delete and recrete to set membership
	resp = requests.delete("https://api.mailgun.net/v2/lists/%s" % current_list, auth=('api', mailgun_api_key))
	print resp.text
	resp = requests.post("https://api.mailgun.net/v2/lists", data={"address": current_list, "name": "Current Guests and Residents", "access_level": "members"}, auth=('api', mailgun_api_key))
	print resp.text

	residents = User.objects.filter(groups__name='residents')
	residents = list(residents)
	resident_emails = []
	for person in residents:
		resident_emails.append(person.email)
	current_emails = guest_emails + resident_emails 
	resp = requests.post("https://api.mailgun.net/v2/lists/%s/members.json" % current_list, 
			data={
				"members":json.dumps(current_emails), 
				"subscribed": True
				},
				auth=('api', mailgun_api_key)
			)
	print resp.text
	resp = requests.get( "https://api.mailgun.net/v2/lists/%s/members" % current_list,
					        auth=('api', mailgun_api_key))
	print resp.text



