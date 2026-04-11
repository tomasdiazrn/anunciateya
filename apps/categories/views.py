from django.shortcuts import render


def placeholder(request):
    """Reserved for future category browsing UI."""
    return render(request, "categories/placeholder.html")
