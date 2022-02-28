from datetime import tzinfo


def end_of_day(datetime):
    end_of_day_datetime = datetime.replace(hour=23, minute=59, second=59, microsecond=999999)
    return end_of_day_datetime

def start_of_day(datetime):
    start_of_day_datetime = datetime.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_of_day_datetime    