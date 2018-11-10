from datetime import datetime


def get_user_name(api, user_id: (int, str), name_case='nom'):
    """
    :param api: VK API object
    :param user_id: user id for parse
    :param name_case: declension for name
    :return: a string with format "First Name Last Name"
    """
    user = api.users.get(user_ids=user_id, name_case=name_case)[0]
    return '{} {}'.format(user['first_name'], user['last_name'])


def parse_user_id(api, user_id: (str, int)):
    """
    :param api: VK API object
    :param user_id: a string for parse
    :return: integer user id
    """
    if user_id.startswith('https://vk.com/'):
        user_id = user_id[15:]
    elif user_id.startswith('vk.com/'):
        user_id = user_id[7:]
    elif user_id.isdecimal():
        user_id = user_id
    else:
        user_id = user_id
    return api.users.get(user_ids=user_id)[0]['id']


def get_times_of_day(variants: (list, set, frozenset)):
    """ Returns string depending about time
    :param variants: a massive with times (Night, Morning, Day, Evening)
    :return: string depending about time
    """
    hours = datetime.now().hour
    if hours in range(0, 6):
        return variants[0]
    elif hours in range(6, 12):
        return variants[1]
    elif hours in range(12, 18):
        return variants[2]
    elif hours in range(18, 24):
        return variants[3]


def plural_form(number: int, variants: (list, tuple)):
    cases = (2, 0, 1, 1, 1, 2)
    """Returns the number and the declined word after it
    :param number: number
    :param variants: variants of the word in the format (for 1, for 2, for 5)
    Пример:
    plural_form(difference.days, ("day", "of the days", "days"))
    :return: The number and the declined word after it
    """
    return f'{number} {variants[2 if (4 < number % 100 < 20) else cases[min(number % 10, 5)]]}'


def get_self_id(api):
    from settings import Settings
    if Settings.auth[0] == 'group':
        return api.groups.getById()[0]['id']
    else:
        return api.users.get()[0]['id']
