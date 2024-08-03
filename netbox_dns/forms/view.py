from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q, Count

from netbox.forms import (
    NetBoxModelBulkEditForm,
    NetBoxModelFilterSetForm,
    NetBoxModelImportForm,
    NetBoxModelForm,
)
from utilities.forms.fields import (
    TagFilterField,
    CSVModelChoiceField,
    CSVModelMultipleChoiceField,
    DynamicModelChoiceField,
    DynamicModelMultipleChoiceField,
)
from utilities.forms import BOOLEAN_WITH_BLANK_CHOICES
from utilities.forms.rendering import FieldSet
from tenancy.models import Tenant
from tenancy.forms import TenancyForm, TenancyFilterForm
from ipam.models import Prefix

from netbox_dns.models import View
from netbox_dns.fields import PrefixDynamicModelMultipleChoiceField
from netbox_dns.utilities import (
    get_ip_addresses_by_prefix,
    update_dns_records,
    get_views_by_prefix,
)


__all__ = (
    "ViewForm",
    "ViewFilterForm",
    "ViewImportForm",
    "ViewBulkEditForm",
)


class ViewPrefixUpdateMixin:
    def clean(self, *args, **kwargs):
        super().clean(*args, **kwargs)

        if self.instance.pk is None or "prefixes" not in self.changed_data:
            return

        prefixes = self.cleaned_data.get("prefixes")
        old_prefixes = View.objects.get(pk=self.instance.pk).prefixes.all()

        for prefix in prefixes.difference(old_prefixes):
            for ip_address in get_ip_addresses_by_prefix(prefix, check_view=False):
                try:
                    update_dns_records(ip_address, commit=False, view=self.instance)
                except ValidationError as exc:
                    self.add_error("prefixes", exc.messages)

        # +
        # Determine the prefixes that, when removed from the view, have no direct view
        # assignment left. These prefixes will potentially inherit from a different view,
        # which means that they have to be validated against different zones.
        # -
        check_prefixes = set(
            old_prefixes.annotate(view_count=Count("netbox_dns_views")).filter(
                Q(view_count=1, netbox_dns_views=self.instance)
                | Q(netbox_dns_views__isnull=True)
            )
        ) - set(prefixes)

        for check_prefix in check_prefixes:
            # +
            # Check whether the prefix will get a new view by inheritance from its
            # parent. If that's the case, the IP addresses need to be checked.
            # -
            if (parent := check_prefix.get_parents().last()) is None:
                return

            for view in get_views_by_prefix(parent):
                if view == self.instance:
                    continue

                for ip_address in get_ip_addresses_by_prefix(
                    check_prefix, check_view=False
                ):
                    try:
                        update_dns_records(ip_address, commit=False, view=view)
                    except ValidationError as exc:
                        self.add_error("prefixes", exc.messages)


class ViewForm(ViewPrefixUpdateMixin, TenancyForm, NetBoxModelForm):
    prefixes = PrefixDynamicModelMultipleChoiceField(
        queryset=Prefix.objects.all(),
        required=False,
        label="IPAM Prefixes",
        context={
            "depth": None,
        },
    )

    fieldsets = (
        FieldSet("name", "default_view", "description", "tags", name="View"),
        FieldSet("tenant_group", "tenant", name="Tenancy"),
        FieldSet("prefixes", name="IPAM"),
    )

    class Meta:
        model = View
        fields = (
            "name",
            "default_view",
            "description",
            "tags",
            "tenant",
            "prefixes",
        )


class ViewFilterForm(TenancyFilterForm, NetBoxModelFilterSetForm):
    model = View
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("name", "default_view", "description", name="Attributes"),
        FieldSet("prefix_id", name="IPAM"),
        FieldSet("tenant_group_id", "tenant_id", name="Tenancy"),
    )

    name = forms.CharField(
        required=False,
    )
    default_view = forms.NullBooleanField(
        required=False,
        widget=forms.Select(choices=BOOLEAN_WITH_BLANK_CHOICES),
    )
    description = forms.CharField(
        required=False,
    )
    prefix_id = PrefixDynamicModelMultipleChoiceField(
        queryset=Prefix.objects.all(),
        required=False,
        label="Prefix",
        context={
            "depth": None,
        },
    )
    tag = TagFilterField(View)


class ViewImportForm(ViewPrefixUpdateMixin, NetBoxModelImportForm):
    prefixes = CSVModelMultipleChoiceField(
        queryset=Prefix.objects.all(),
        to_field_name="id",
        required=False,
        help_text="Prefix IDs assigned to the view",
    )
    tenant = CSVModelChoiceField(
        queryset=Tenant.objects.all(),
        to_field_name="name",
        required=False,
        help_text="Assigned tenant",
    )

    class Meta:
        model = View
        fields = ("name", "description", "prefixes", "tenant", "tags")


class ViewBulkEditForm(NetBoxModelBulkEditForm):
    model = View

    description = forms.CharField(max_length=200, required=False)
    tenant = DynamicModelChoiceField(queryset=Tenant.objects.all(), required=False)
    prefixes = PrefixDynamicModelMultipleChoiceField(
        queryset=Prefix.objects.all(),
        required=False,
        label="IPAM Prefixes",
        context={
            "depth": None,
        },
    )

    fieldsets = (
        FieldSet(
            "name",
            "description",
            name="Attributes",
        ),
        FieldSet("tenant", name="Tenancy"),
    )

    nullable_fields = ("description", "tenant")
