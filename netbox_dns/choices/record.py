from dns import rdatatype, rdataclass

from utilities.choices import ChoiceSet


def initialize_choice_names(cls):
    for choice in cls.CHOICES:
        setattr(cls, choice[0], choice[0])
    return cls


@initialize_choice_names
class RecordTypeChoices(ChoiceSet):
    CHOICES = [
        (rdtype.name, rdtype.name)
        for rdtype in sorted(rdatatype.RdataType, key=lambda a: a.name)
        if not rdatatype.is_metatype(rdtype)
    ]
    SINGLETONS = [
        rdtype.name for rdtype in rdatatype.RdataType if rdatatype.is_singleton(rdtype)
    ]


@initialize_choice_names
class RecordClassChoices(ChoiceSet):
    CHOICES = [
        (rdclass.name, rdclass.name)
        for rdclass in sorted(rdataclass.RdataClass)
        if not rdataclass.is_metaclass(rdclass)
    ]


class RecordStatusChoices(ChoiceSet):
    key = "Record.status"

    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"

    CHOICES = [
        (STATUS_ACTIVE, "Active", "blue"),
        (STATUS_INACTIVE, "Inactive", "red"),
    ]
