#!/data/data/com.termux/files/usr/bin/python
"""
Persian to Gregorian Date Converter with Days Since Calculator
Converts Persian (Solar Hijri) dates to Gregorian dates and calculates days since
"""

import sys
import datetime


class PersianDateConverter:
    """Converts Persian (Solar Hijri) dates to Gregorian dates"""

    # Persian month names
    PERSIAN_MONTHS = [
        "Farvardin",
        "Ordibehesht",
        "Khordad",
        "Tir",
        "Mordad",
        "Shahrivar",
        "Mehr",
        "Aban",
        "Azar",
        "Dey",
        "Bahman",
        "Esfand",
    ]

    # Persian month lengths (31 days for first 6 months, 30 for next 5, 29/30 for last)
    PERSIAN_MONTH_LENGTHS = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]

    @staticmethod
    def is_persian_leap_year(year):
        """Check if a Persian year is a leap year"""
        # Persian leap year calculation using 33-year cycle
        return (year * 33 + 33) % 132 < 6

    @staticmethod
    def persian_to_gregorian(persian_year, persian_month, persian_day):
        """
        Convert Persian date to Gregorian date

        Args:
            persian_year: Persian year (e.g., 1404)
            persian_month: Persian month (1-12)
            persian_day: Persian day (1-31)

        Returns:
            tuple: (year, month, day) in Gregorian calendar

        Raises:
            ValueError: If date is invalid
        """
        # Validate inputs
        if persian_month < 1 or persian_month > 12:
            raise ValueError(f"Month must be between 1 and 12, got {persian_month}")

        # Check day validity for the given month
        max_day = PersianDateConverter.PERSIAN_MONTH_LENGTHS[persian_month - 1]
        if persian_month == 12 and PersianDateConverter.is_persian_leap_year(persian_year):
            max_day = 30  # Esfand has 30 days in leap years

        if persian_day < 1 or persian_day > max_day:
            raise ValueError(f"Day must be between 1 and {max_day} for month {persian_month}, got {persian_day}")

        # Convert Persian date to days since 1/1/1
        days = 0
        for year in range(1, persian_year):
            if PersianDateConverter.is_persian_leap_year(year):
                days += 366
            else:
                days += 365

        # Add days for months of the current year
        for month in range(1, persian_month):
            month_length = PersianDateConverter.PERSIAN_MONTH_LENGTHS[month - 1]
            if month == 12 and PersianDateConverter.is_persian_leap_year(persian_year):
                month_length = 30
            days += month_length

        # Add days of current month
        days += persian_day - 1

        # Reference: Persian date 1/1/1 = Gregorian 622/3/19
        ref_date = datetime.date(622, 3, 19)

        # Convert to Gregorian date
        result_date = ref_date + datetime.timedelta(days=days)

        return result_date.year, result_date.month, result_date.day

    @staticmethod
    def days_since(gregorian_year, gregorian_month, gregorian_day):
        """
        Calculate days from a given date to today

        Args:
            gregorian_year, gregorian_month, gregorian_day: Gregorian date

        Returns:
            int: Number of days since the date (0 if today, negative if future)
            datetime.date: The date object of the input
        """
        input_date = datetime.date(gregorian_year, gregorian_month, gregorian_day)
        today = datetime.date.today()

        delta = today - input_date
        return delta.days, input_date, today

    @staticmethod
    def format_days_since(days):
        """Format days since into a human-readable string"""
        if days < 0:
            return f"{abs(days)} days in the future"
        elif days == 0:
            return "Today!"
        elif days == 1:
            return "1 day ago (yesterday)"
        elif days < 7:
            return f"{days} days ago"
        elif days < 30:
            weeks = days // 7
            remaining_days = days % 7
            if remaining_days == 0:
                return f"{weeks} weeks ago"
            else:
                return f"{weeks} weeks and {remaining_days} days ago"
        elif days < 365:
            months = days // 30
            remaining_days = days % 30
            if remaining_days == 0:
                return f"{months} months ago"
            else:
                return f"{months} months and {remaining_days} days ago"
        else:
            years = days // 365
            remaining_days = days % 365
            months = remaining_days // 30
            remaining_days = remaining_days % 30

            if months == 0 and remaining_days == 0:
                return f"{years} years ago"
            elif months == 0:
                return f"{years} years and {remaining_days} days ago"
            elif remaining_days == 0:
                return f"{years} years and {months} months ago"
            else:
                return f"{years} years, {months} months, and {remaining_days} days ago"

    @staticmethod
    def format_persian_date(year, month, day):
        """Format Persian date as string"""
        month_name = PersianDateConverter.PERSIAN_MONTHS[month - 1]
        return f"{year}/{month:02d}/{day:02d} ({month_name})"


def main():
    """Main function to handle command line arguments"""
    if len(sys.argv) != 4:
        print("Usage: python convert_date.py <day> <month> <year>")
        print("Example: python convert_date.py 10 12 1404")
        print("         (Converts 10/12/1404 Persian to Gregorian)")
        print("\nNote: Date format is day month year (Persian calendar)")
        sys.exit(1)

    try:
        day = int(sys.argv[1])
        month = int(sys.argv[2])
        year = int(sys.argv[3])

        # Validate day and month ranges
        if day < 1 or day > 31:
            print("Error: Day must be between 1 and 31")
            sys.exit(1)

        if month < 1 or month > 12:
            print("Error: Month must be between 1 and 12")
            sys.exit(1)

        # Convert Persian to Gregorian
        converter = PersianDateConverter()
        gregorian_year, gregorian_month, gregorian_day = converter.persian_to_gregorian(year, month, day)

        # Calculate days since
        days_since, input_date, today = converter.days_since(gregorian_year, gregorian_month, gregorian_day)

        # Format output with separator
        print("=" * 60)
        print("📅 PERSIAN TO GREGORIAN DATE CONVERTER")
        print("=" * 60)

        # Persian date
        persian_date_str = converter.format_persian_date(year, month, day)
        print(f"\n🇮🇷 Persian date:  {persian_date_str}")

        # Gregorian date
        gregorian_date_str = f"{gregorian_year}/{gregorian_month:02d}/{gregorian_day:02d}"
        print(f"🌍 Gregorian date: {gregorian_date_str}")

        # Weekday
        weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        weekday = weekday_names[input_date.weekday()]
        print(f"📆 Weekday:       {weekday}")

        # Days since with formatted output
        print("\n" + "-" * 60)
        print("📊 DAYS SINCE CALCULATION")
        print("-" * 60)

        print(f"\n📅 Input date:    {gregorian_date_str}")
        print(f"📅 Today:         {today.strftime('%Y/%m/%d')}")
        print(f"📊 Days since:    {days_since:,} days")
        print(f"📝 Human format:  {converter.format_days_since(days_since)}")

        # Additional statistics if date is in the past
        if days_since > 0:
            print("\n📈 STATISTICS:")
            print(f"   • Weeks:       {days_since // 7:,} weeks")
            print(f"   • Months:      {days_since // 30:,} months (approx)")
            print(f"   • Years:       {days_since / 365:.2f} years (approx)")
        elif days_since == 0:
            print("\n🎉 Today's date! No time has passed.")
        else:
            print(f"\n⏳ This date is {abs(days_since)} days in the future.")

        print("\n" + "=" * 60)

    except ValueError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
