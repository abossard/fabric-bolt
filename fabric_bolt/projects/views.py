"""
Views for the Projects App
"""

import datetime
import subprocess
import sys
from copy import deepcopy

from django.http import HttpResponseRedirect, StreamingHttpResponse
from django.db.models.aggregates import Count
from django.contrib import messages
from django.views.generic import CreateView, UpdateView, DetailView, DeleteView, RedirectView, View
from django.core.urlresolvers import reverse_lazy, reverse
from django.shortcuts import get_object_or_404
from django.forms import CharField, PasswordInput, Select, FloatField, BooleanField
from django.conf import settings
from django.core.cache import cache

from django_tables2 import RequestConfig, SingleTableView

from fabric_bolt.core.mixins.views import MultipleGroupRequiredMixin
from fabric_bolt.hosts.models import Host
from fabric_bolt.projects import forms, tables, models
from fabric_bolt.projects.util import get_fabric_tasks, build_command, get_task_details
from fabric_bolt.web_hooks.tables import HookTable
from fabric_bolt.projects.signals import deployment_finished
from copy import deepcopy


class ProjectSubPageMixin(object):
    """
    View mixin which adds self.project on the view, and {project} in the template.
    assumes project_id is defined in url.
    """

    def dispatch(self, request, *args, **kwargs):
        self.project = get_object_or_404(models.Project, id=kwargs['project_id'])
        return super(ProjectSubPageMixin, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ProjectSubPageMixin, self).get_context_data(**kwargs)
        context['project'] = self.project
        return context


class StageSubPageMixin(ProjectSubPageMixin):
    """
    View mixin which adds self.project and self.stage on the view, and {project} and {stage} in the template.
    assumes project_id and stage_id are defined in url.
    """

    def dispatch(self, request, *args, **kwargs):
        self.project = get_object_or_404(models.Project, id=kwargs['project_id'])
        self.stage = get_object_or_404(models.Stage, id=kwargs['stage_id'], project=self.project)
        return super(StageSubPageMixin, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(StageSubPageMixin, self).get_context_data(**kwargs)
        context['stage'] = self.stage
        context['project'] = self.project
        return context


class ProjectList(SingleTableView):
    """
    Project List page
    """

    table_class = tables.ProjectTable
    model = models.Project
    queryset = models.Project.active_records.all()


class ProjectCreate(CreateView):
    """
    Create a new project
    """
    group_required = ['Admin', 'Deployer', ]
    model = models.Project
    form_class = forms.ProjectCreateForm
    template_name_suffix = '_create'

    def form_valid(self, form):
        """After the form is valid lets let people know"""

        ret = super(ProjectCreate, self).form_valid(form)

        # Good to make note of that
        messages.add_message(self.request, messages.SUCCESS, 'Project %s created' % self.object.name)

        return ret

class ProjectCopy(MultipleGroupRequiredMixin, CreateView):
    """
    Copy project
    """
    group_required = ['Admin', 'Deployer', ]
    model = models.Project
    form_class = forms.ProjectCreateForm
    template_name_suffix = '_copy'
    copy_object = None

    def get_initial(self):
        """
        Returns the initial data to use for forms on this view.
        """
        initial = super(ProjectCopy, self).get_initial()
        if self.copy_object:
            initial.update({'name': '%s copy' % self.copy_object.name,
                            'description': self.copy_object.description,
                            'use_repo_fabfile': self.copy_object.use_repo_fabfile,
                            'fabfile_requirements': self.copy_object.fabfile_requirements,
                            'repo_url': self.copy_object.repo_url})
        return initial

    def get(self, request, *args, **kwargs):
        self.copy_object = self.get_object()
        return super(ProjectCopy, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.copy_object = self.get_object()
        return super(ProjectCopy, self).post(request, *args, **kwargs)

    def copy_relations(self):
        """"
        Copy relations objects:  Configuration, Stages
        """
        if self.copy_object:
            # copy project configurations
            self.copy_configurations()
            # copy stages
            self.copy_stages()

    def copy_configurations(self, stages=None):
        """
        Copy configuretions
        """
        if stages:
            confs = stages[0].stage_configurations()
            new_stage = stages[1]
        else:
            confs = self.copy_object.project_configurations()
            new_stage = None

        for conf in confs:
            new_conf = deepcopy(conf)
            new_conf.id = None
            new_conf.project = self.object
            new_conf.stage = new_stage
            new_conf.save()


    def copy_stages(self):
        stages = self.copy_object.get_stages()
        for stage in stages:
            new_stage = deepcopy(stage)
            new_stage.id = None
            new_stage.project=self.object
            new_stage.save()
            new_stage.hosts = stage.hosts.all()
            self.copy_configurations(stages=[stage, new_stage])


    def form_valid(self, form):
        """After the form is valid lets let people know"""

        ret = super(ProjectCopy, self).form_valid(form)
        self.copy_relations()

        # Good to make note of that
        messages.add_message(self.request, messages.SUCCESS, 'Project %s copied' % self.object.name)

        return ret

class ProjectDetail(DetailView):
    """
    Display the Project Detail/Summary page: Configurations, Stages, and Deployments
    """

    model = models.Project

    def dispatch(self, request, *args, **kwargs):
        if request.user.user_is_historian():
            self.template_name = "projects/historian_detail.html"

        return super(ProjectDetail, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ProjectDetail, self).get_context_data(**kwargs)

        stages = self.object.get_stages().annotate(deployment_count=Count('deployment'))
        context['stages'] = stages

        stage_table = tables.StageTable(stages, prefix='stage_')

        RequestConfig(self.request).configure(stage_table)
        context['stage_table'] = stage_table

        deployment_table = tables.DeploymentTable(models.Deployment.objects.filter(stage__in=stages).select_related('stage', 'task'), prefix='deploy_')
        RequestConfig(self.request).configure(deployment_table)
        context['deployment_table'] = deployment_table

        hook_table = HookTable(self.object.web_hooks(False))
        RequestConfig(self.request).configure(hook_table)
        context['hook_table'] = hook_table

        return context


class ProjectUpdate(UpdateView):
    """
    Update a project
    """
    group_required = ['Admin', 'Deployer', ]
    model = models.Project
    form_class = forms.ProjectUpdateForm
    template_name_suffix = '_update'
    success_url = reverse_lazy('projects_project_list')


class ProjectDelete(DeleteView):
    """
    Deletes a project by setting the Project's date_deleted. We save projects for historical tracking.
    """
    group_required = ['Admin', ]
    model = models.Project

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.date_deleted = datetime.datetime.now()
        self.object.save()

        messages.add_message(request, messages.WARNING, 'Project {} Successfully Deleted'.format(self.object))
        return HttpResponseRedirect(reverse('projects_project_list'))


class ProjectConfigurationList(ProjectSubPageMixin, SingleTableView):
    """
    Project Configuration List page
    """

    table_class = tables.ConfigurationTable
    model = models.Configuration

    def get_queryset(self):
        return self.project.project_configurations()


class ProjectConfigurationCreate(MultipleGroupRequiredMixin, ProjectSubPageMixin, CreateView):
    """
    Create a Project Configuration. These are used to set the Fabric env object for a task.
    """
    group_required = ['Admin', ]
    model = models.Configuration
    template_name_suffix = '_create'
    form_class = forms.ConfigurationCreateForm

    def form_valid(self, form):
        """Set the project on this configuration after it's valid"""

        self.object = form.save(commit=False)
        self.object.project = self.project

        if self.kwargs.get('stage_id', None):
            current_stage = models.Stage.objects.get(pk=self.kwargs.get('stage_id'))
            self.object.stage = current_stage

        self.object.save()

        # Good to make note of that
        messages.add_message(self.request, messages.SUCCESS, 'Configuration %s created' % self.object.key)

        return super(ProjectConfigurationCreate, self).form_valid(form)

    def get_success_url(self):
        success_url = super(ProjectConfigurationCreate, self).get_success_url()

        if self.object.stage:
            success_url = reverse('projects_stage_view', args=(self.object.pk, self.object.stage.pk))

        return success_url


class ProjectConfigurationUpdate(MultipleGroupRequiredMixin, ProjectSubPageMixin, UpdateView):
    """
    Update a Project Configuration
    """
    group_required = ['Admin', ]
    model = models.Configuration
    template_name_suffix = '_update'
    form_class = forms.ConfigurationUpdateForm


class ProjectConfigurationDelete(MultipleGroupRequiredMixin, ProjectSubPageMixin, DeleteView):
    """
    Delete a project configuration from a project
    """
    group_required = ['Admin', ]
    model = models.Configuration

    def dispatch(self, request, *args, **kwargs):

        return super(ProjectConfigurationDelete, self).dispatch(request, *args, **kwargs)

    def get_success_url(self):
        """Get the url depending on what type of configuration I deleted."""
        if self.stage_id:
            url = reverse('projects_stage_view', args=(self.project_id, self.stage_id))
        else:
            url = reverse('projects_project_view', args=(self.project_id,))

        return url

    def delete(self, request, *args, **kwargs):

        obj = self.get_object()

        # Save where I was before I go and delete myself
        self.project_id = obj.project.pk
        self.stage_id = obj.stage.pk if obj.stage else None

        messages.success(self.request, 'Configuration {} Successfully Deleted'.format(self.get_object()))
        return super(ProjectConfigurationDelete, self).delete(self, request, *args, **kwargs)


class ProjectDeploymentList(ProjectSubPageMixin, SingleTableView):
    """
    Project Deployment List page
    """

    table_class = tables.DeploymentTable
    model = models.Deployment

    def get_queryset(self):
        return models.Deployment.objects.filter(stage__project=self.project).select_related('stage', 'task')


class DeploymentCreate(MultipleGroupRequiredMixin, CreateView):
    """
    Form to create a new Deployment for a Project Stage. POST will kick off the DeploymentOutputStream view.
    """
    group_required = ['Admin', 'Deployer', ]
    model = models.Deployment
    form_class = forms.DeploymentForm

    def dispatch(self, request, *args, **kwargs):
        self.project = get_object_or_404(models.Project, id=kwargs['project_id'])
        self.stage = get_object_or_404(models.Stage, id=self.kwargs['stage_id'], project=self.project)
        task_details = get_task_details(self.project, self.kwargs['task_name'])

        if task_details is None:
            messages.error(self.request, '"{}" is not a valid task.'. format(self.kwargs['task_name']))
            return HttpResponseRedirect(
                reverse('projects_stage_view', kwargs={'project_id': self.stage.project_id, 'pk': self.stage.pk})
            )

        self.task_name, self.task_description, self.task_args = task_details

        return super(DeploymentCreate, self).dispatch(request, *args, **kwargs)

    def get_form(self, form_class):

        stage_configurations = self.stage.get_queryset_configurations()

        form = form_class(**self.get_form_kwargs())

        used_arg_names = []

        # We want to inject fields into the form for the configurations they've marked as prompt
        for config in stage_configurations:
            if config.task_argument and config.task_name != self.task_name:
                continue

            if not config.prompt_me_for_input:
                if config.task_argument:
                    used_arg_names.append(config.key)
                continue

            str_config_key = 'configuration_value_for_{}'.format(config.key)

            if config.data_type == config.BOOLEAN_TYPE:
                field = BooleanField(widget=Select(choices=((False, 'False'), (True, 'True'))))
                field.coerce=lambda x: x == 'True',
            elif config.data_type == config.NUMBER_TYPE:
                field = FloatField()
            else:
                field = CharField()

                if config.sensitive_value:
                    field.widget = PasswordInput()

                if config.task_argument:
                    used_arg_names.append(config.key)
                    field.label = 'Argument value for ' + config.key

            field.initial = config.value

            form.fields[str_config_key] = field
            form.helper.layout.fields.insert(len(form.helper.layout.fields)-1, str_config_key)

        for arg in self.task_args:
            if isinstance(arg, tuple):
                name, default = arg
                required = False
            else:
                name, default = arg, None
                required = True

            if name in used_arg_names:
                continue

            str_config_key = 'configuration_value_for_{}'.format(name)

            field = CharField(label='Argument value for ' + name, initial=default,
                              required=required)

            form.fields[str_config_key] = field
            form.helper.layout.fields.insert(len(form.helper.layout.fields)-1, str_config_key)

        return form

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.stage = self.stage

        self.object.task, created = models.Task.objects.get_or_create(
            name=self.task_name,
            defaults={'description': self.task_description}
        )

        if not created:
            self.object.task.times_used += 1
            self.object.task.description = self.task_description
            self.object.task.save()

        self.object.user = self.request.user
        self.object.save()

        configuration_values = {}
        for key, value in form.cleaned_data.iteritems():
            if key.startswith('configuration_value_for_'):
                configuration_values[key.replace('configuration_value_for_', '')] = value

        self.request.session['configuration_values'] = configuration_values

        return super(DeploymentCreate, self).form_valid(form)

    def get_context_data(self, **kwargs):
        context = super(DeploymentCreate, self).get_context_data(**kwargs)

        context['stage'] = self.stage
        context['project'] = self.project
        context['configs'] = self.stage.get_queryset_configurations(prompt_me_for_input=False)
        context['task_name'] = self.task_name
        context['task_description'] = self.task_description

        return context

    def get_success_url(self):
        return reverse('projects_deployment_detail', kwargs={'project_id': self.project.pk, 'stage_id': self.stage.id,
                                                             'pk': self.object.pk})


class DeploymentDetail(StageSubPageMixin, DetailView):
    """
    Display the detail/summary of a deployment
    """
    model = models.Deployment

    def get_template_names(self):
        if getattr(settings, 'SOCKETIO_ENABLED', False):
            return ['projects/deployment_detail_socketio.html']
        else:
            return ['projects/deployment_detail.html']


class DeploymentOutputStream(StageSubPageMixin, View):
    """
    Deployment view does the heavy lifting of calling Fabric Task for a Project Stage
    """

    def output_stream_generator(self):
        if get_task_details(self.project, self.object.task.name) is None:
            return

        try:
            process = subprocess.Popen(
                build_command(self.object, self.request.session),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=True
            )

            all_output = ''
            while True:
                nextline = process.stdout.readline()
                if nextline == '' and process.poll() != None:
                    break

                all_output += nextline

                yield '<span style="color:rgb(200, 200, 200);font-size: 14px;font-family: \'Helvetica Neue\', Helvetica, Arial, sans-serif;">{} </span><br /> {}'.format(nextline, ' '*1024)
                sys.stdout.flush()

            self.object.status = self.object.SUCCESS if process.returncode == 0 else self.object.FAILED

            yield '<span id="finished" style="display:none;">{}</span> {}'.format(self.object.status, ' '*1024)

            self.object.output = all_output
            self.object.save()

            deployment_finished.send(self.object, deployment_id=self.object.pk)

        except Exception as e:
            message = "An error occurred: " + e.message
            yield '<span style="color:rgb(200, 200, 200);font-size: 14px;font-family: \'Helvetica Neue\', Helvetica, Arial, sans-serif;">{} </span><br /> {}'.format(message, ' '*1024)
            yield '<span id="finished" style="display:none;">failed</span> {}'.format('*1024')

    def get(self, request, *args, **kwargs):
        self.object = get_object_or_404(
            models.Deployment,
            stage=self.stage,
            pk=int(kwargs['pk']),
            status=models.Deployment.PENDING
        )
        resp = StreamingHttpResponse(self.output_stream_generator())
        return resp


class ProjectStageList(ProjectSubPageMixin, SingleTableView):
    """
    Project Stage List page
    """

    table_class = tables.StageTable
    model = models.Stage

    def get_queryset(self):
        return self.project.get_stages().annotate(deployment_count=Count('deployment'))


class ProjectStageCreate(MultipleGroupRequiredMixin, ProjectSubPageMixin, CreateView):
    """
    Create/Add a Stage to a Project
    """
    group_required = ['Admin', ]
    model = models.Stage
    template_name_suffix = '_create'
    form_class = forms.StageCreateForm

    def form_valid(self, form):
        """Set the project on this configuration after it's valid"""

        self.object = form.save(commit=False)
        self.object.project = self.project
        self.object.save()

        # Good to make note of that
        messages.add_message(self.request, messages.SUCCESS, 'Stage %s created' % self.object.name)

        return super(ProjectStageCreate, self).form_valid(form)


class ProjectStageUpdate(MultipleGroupRequiredMixin, ProjectSubPageMixin, UpdateView):
    """
    Project Stage Update form
    """
    group_required = ['Admin', 'Deployer', ]
    model = models.Stage
    template_name_suffix = '_update'
    form_class = forms.StageUpdateForm


class ProjectStageView(ProjectSubPageMixin, DetailView):
    """
    Display the details on a project stage: List Hosts, Configurations, and Tasks available to run
    """

    model = models.Stage

    def get_context_data(self, **kwargs):

        context = super(ProjectStageView, self).get_context_data(**kwargs)

        # Hosts Table (Stage->Host Through table)
        stage_hosts = self.object.hosts.all()

        host_table = tables.StageHostTable(stage_hosts, stage_id=self.object.pk, project_id=self.project.pk)  # Through table
        RequestConfig(self.request).configure(host_table)
        context['hosts'] = host_table

        context['available_hosts'] = Host.objects.exclude(id__in=[host.pk for host in stage_hosts]).all()

        return context


class ProjectStageTasksAjax(ProjectSubPageMixin, DetailView):
    model = models.Stage
    template_name = 'projects/stage_tasks_snippet.html'

    def get_context_data(self, **kwargs):
        context = super(ProjectStageTasksAjax, self).get_context_data(**kwargs)

        all_tasks = get_fabric_tasks(self.object.project)
        task_names = [x[0] for x in all_tasks]

        context['all_tasks'] = task_names
        context['frequent_tasks_run'] = models.Task.objects.filter(
            name__in=task_names
        ).order_by('-times_used')[:5]

        return context


class ProjectStageDelete(MultipleGroupRequiredMixin, ProjectSubPageMixin, DeleteView):
    """
    Delete a project stage
    """
    group_required = ['Admin', ]
    model = models.Stage

    def dispatch(self, request, *args, **kwargs):
        return super(ProjectStageDelete, self).dispatch(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.date_deleted = datetime.datetime.now()
        self.object.save()

        messages.add_message(request, messages.WARNING, 'Stage {} Successfully Deleted'.format(self.object))
        return HttpResponseRedirect(reverse('projects_project_view', args=(self.object.project.pk,)))


class StageDeploymentList(StageSubPageMixin, SingleTableView):
    """
    Project Deployment List page
    """

    table_class = tables.DeploymentTable
    model = models.Deployment
    template_name_suffix = '_stage_list'

    def get_queryset(self):
        return models.Deployment.objects.filter(stage=self.stage).select_related('stage', 'task')

    def get_table(self, **kwargs):
        table = super(StageDeploymentList, self).get_table(**kwargs)
        table.base_columns['stage'].visible = False
        return table


class StageConfigurationList(StageSubPageMixin, SingleTableView):
    """
    Stage Configuration List page
    """

    table_class = tables.ConfigurationTable
    model = models.Configuration
    template_name_suffix = '_stage_list'

    def get_queryset(self):
        return self.stage.stage_configurations()


class ProjectStageMapHost(MultipleGroupRequiredMixin, StageSubPageMixin, RedirectView):
    """
    Map a Project Stage to a Host
    """
    group_required = ['Admin',]
    permanent = False

    def get(self, request, *args, **kwargs):
        host_id = kwargs.get('host_id')

        self.stage.hosts.add(Host.objects.get(pk=host_id))

        return super(ProjectStageMapHost, self).get(request, *args, **kwargs)

    def get_redirect_url(self, **kwargs):
        return reverse('projects_stage_view', args=(self.project.pk, self.stage.pk,))


class ProjectStageUnmapHost(MultipleGroupRequiredMixin, StageSubPageMixin, RedirectView):
    """
    Unmap a Project Stage from a Host (deletes the Stage->Host through table record)
    """
    group_required = ['Admin', ]
    permanent = False

    def get(self, request, *args, **kwargs):
        host_id = kwargs.get('host_id')

        host = Host.objects.get(pk=int(host_id))
        self.stage.hosts.remove(host)

        return super(ProjectStageUnmapHost, self).get(request, *args, **kwargs)

    def get_redirect_url(self, **kwargs):
        return reverse('projects_stage_view', args=(self.project.pk, self.stage.pk,))


class ProjectInvalidateCache(RedirectView):
    permanent = False

    def get(self, request, *args, **kwargs):
        self.project_id = kwargs.get('pk')

        cache.delete_many(['project_{}_fabfile_tasks'.format(self.project_id),
                           'project_{}_fabfile_path'.format(self.project_id)])

        messages.info(request, "Tasks cache invalidated.")

        return super(ProjectInvalidateCache, self).get(request, *args, **kwargs)

    def get_redirect_url(self, **kwargs):
        return reverse('projects_project_view', args=(self.project_id,))
