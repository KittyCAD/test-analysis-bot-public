from django.db import connection
from django.http import HttpResponse


def ping(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return HttpResponse("pong")
    except Exception as e:
        return HttpResponse(f"Database error: {str(e)}", status=500)
