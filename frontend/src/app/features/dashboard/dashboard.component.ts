import { CommonModule } from '@angular/common';
import { Component, HostListener, OnDestroy, OnInit, computed, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import {
  LucideAlertCircle,
  LucideCalendarClock,
  LucideCheckCircle2,
  LucideClock3,
  LucideCopy,
  LucideHistory,
  LucideLayoutDashboard,
  LucideLogOut,
  LucideMegaphone,
  LucidePlus,
  LucideRefreshCcw,
  LucideSave,
  LucideTrash2,
  LucideUserRound,
  LucideUsersRound,
  LucideWifi
} from '@lucide/angular';

import { AuthService } from '../../core/auth.service';
import {
  AdminCallCenterLocation,
  AsteriskFamilyPreview,
  AsteriskImportPreview,
  AsteriskInspectResult,
  CallCenterLocation,
  CurrentUser,
  ScheduleSyncJob,
  Tenant,
  ScheduleChangeLog,
  SchedulePreviewAction,
  ScheduleSnapshot,
  TimeRange,
  Weekday
} from '../../core/models';
import { ScheduleApiService } from '../../core/schedule-api.service';

interface WeekdayOption {
  day: Weekday;
  label: string;
  shortLabel: string;
}

interface ScheduleRule {
  id: number;
  days: Weekday[];
  ranges: TimeRange[];
}

type ScheduleDays = Record<Weekday, TimeRange[]>;
type ActiveModule = 'dashboard' | 'schedule' | 'admin';

const weekdays: WeekdayOption[] = [
  { day: 'Mon', label: 'Lunes', shortLabel: 'Lun' },
  { day: 'Tue', label: 'Martes', shortLabel: 'Mar' },
  { day: 'Wed', label: 'Miércoles', shortLabel: 'Mié' },
  { day: 'Thu', label: 'Jueves', shortLabel: 'Jue' },
  { day: 'Fri', label: 'Viernes', shortLabel: 'Vie' },
  { day: 'Sat', label: 'Sábado', shortLabel: 'Sáb' },
  { day: 'Sun', label: 'Domingo', shortLabel: 'Dom' }
];

const workdays: Weekday[] = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];
const timePattern = /^([01]\d|2[0-3]):[0-5]\d$/;

function emptyScheduleDays(): ScheduleDays {
  return {
    Mon: [],
    Tue: [],
    Wed: [],
    Thu: [],
    Fri: [],
    Sat: [],
    Sun: []
  };
}

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    LucideAlertCircle,
    LucideCalendarClock,
    LucideCheckCircle2,
    LucideClock3,
    LucideCopy,
    LucideHistory,
    LucideLayoutDashboard,
    LucideLogOut,
    LucideMegaphone,
    LucidePlus,
    LucideRefreshCcw,
    LucideSave,
    LucideTrash2,
    LucideUserRound,
    LucideUsersRound,
    LucideWifi
  ],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css'
})
export class DashboardComponent implements OnInit, OnDestroy {
  readonly weekdays = weekdays;
  readonly user = signal<CurrentUser | null>(null);
  readonly activeModule = signal<ActiveModule>('schedule');
  readonly locations = signal<CallCenterLocation[]>([]);
  readonly selectedLocation = signal<CallCenterLocation | null>(null);
  readonly scheduleRules = signal<ScheduleRule[]>([]);
  readonly changeLogs = signal<ScheduleChangeLog[]>([]);
  readonly reason = signal('');
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly previewLoading = signal(false);
  readonly previewActions = signal<SchedulePreviewAction[]>([]);
  readonly syncStatus = signal<'pending' | 'synced' | 'failed' | null>(null);
  readonly lastSyncError = signal('');
  readonly statusMessage = signal('');
  readonly errorMessage = signal('');
  readonly adminTenants = signal<Tenant[]>([]);
  readonly adminLocations = signal<AdminCallCenterLocation[]>([]);
  readonly asteriskInspect = signal<AsteriskInspectResult | null>(null);
  readonly importPreview = signal<AsteriskImportPreview | null>(null);
  readonly syncJobs = signal<ScheduleSyncJob[]>([]);
  readonly adminLoading = signal(false);
  readonly adminActionLoading = signal(false);
  readonly adminStatusMessage = signal('');
  readonly adminErrorMessage = signal('');
  readonly tenantForm = signal({ name: '', code: '' });
  readonly locationForm = signal({
    tenant_id: 0,
    name: '',
    code: '',
    astdb_family: ''
  });
  readonly importForm = signal({
    tenant_code: 'pas',
    tenant_name: 'PAS',
    family: ''
  });

  private nextRuleId = 1;
  private statusMessageTimer: ReturnType<typeof setTimeout> | null = null;
  private adminStatusMessageTimer: ReturnType<typeof setTimeout> | null = null;
  private readonly originalScheduleDays = signal<ScheduleDays>(emptyScheduleDays());

  readonly roleLabel = computed(() => {
    const currentUser = this.user();

    if (!currentUser) {
      return '';
    }

    return currentUser.is_superuser ? 'Superadmin' : 'Admin tenant';
  });

  readonly selectedLocationId = computed(() => this.selectedLocation()?.id ?? null);

  readonly assignedDays = computed(() => {
    const days = new Set<Weekday>();

    for (const rule of this.scheduleRules()) {
      for (const day of rule.days) {
        days.add(day);
      }
    }

    return days;
  });

  readonly openDaysCount = computed(() => this.assignedDays().size);
  readonly closedDaysCount = computed(() => weekdays.length - this.assignedDays().size);
  readonly activeRulesCount = computed(() => this.scheduleRules().length);
  readonly totalRangesCount = computed(() =>
    this.scheduleRules().reduce((total, rule) => total + rule.ranges.length, 0)
  );
  readonly unassignedDayLabels = computed(() => {
    const assignedDays = this.assignedDays();
    const labels = weekdays
      .filter(({ day }) => !assignedDays.has(day))
      .map(({ shortLabel }) => shortLabel);

    return labels.length > 0 ? labels.join(', ') : 'Ninguno';
  });
  readonly hasAvailableDays = computed(() => this.assignedDays().size < weekdays.length);
  readonly syncStatusLabel = computed(() => {
    switch (this.syncStatus()) {
      case 'synced':
        return 'Sincronizado';
      case 'failed':
        return 'Fallido';
      case 'pending':
        return 'Pendiente';
      default:
        return 'Sin estado';
    }
  });
  readonly hasScheduleChanges = computed(() =>
    this.daysForUpdate().some(
      ({ day_of_week, ranges }) => this.rangesKey(ranges) !== this.rangesKey(this.originalScheduleDays()[day_of_week])
    )
  );
  readonly isSuperuser = computed(() => this.user()?.is_superuser ?? false);
  readonly pendingJobsCount = computed(() =>
    this.syncJobs().filter((job) => job.status === 'pending').length
  );
  readonly failedJobsCount = computed(() =>
    this.syncJobs().filter((job) => job.status === 'failed').length
  );

  constructor(
    private readonly auth: AuthService,
    private readonly api: ScheduleApiService,
    private readonly router: Router
  ) {}

  ngOnInit(): void {
    this.loading.set(true);
    this.auth.me().subscribe({
      next: (user) => {
        this.user.set(user);
        this.loadLocations();
      },
      error: () => {
        this.loading.set(false);
        void this.router.navigateByUrl('/login');
      }
    });
  }

  ngOnDestroy(): void {
    this.clearStatusMessageTimer();
    this.clearAdminStatusMessageTimer();
  }

  selectLocation(location: CallCenterLocation): void {
    this.selectedLocation.set(location);
    this.reason.set('');
    this.previewActions.set([]);
    this.syncStatus.set(null);
    this.lastSyncError.set('');
    this.statusMessage.set('');
    this.errorMessage.set('');
    this.loadSchedule(location.id);
    this.loadChangeLogs(location.id);
  }

  selectLocationById(locationId: number | string): void {
    const numericLocationId = Number(locationId);
    const location = this.locations().find((item) => item.id === numericLocationId);

    if (location) {
      this.selectLocation(location);
    }
  }

  refreshSelected(): void {
    if (this.activeModule() === 'admin') {
      this.loadAdminData();
      return;
    }

    const location = this.selectedLocation();

    if (!location) {
      return;
    }

    this.loadSchedule(location.id);
    this.loadChangeLogs(location.id);
  }

  selectModule(module: ActiveModule): void {
    if (module === 'admin' && !this.isSuperuser()) {
      return;
    }

    this.activeModule.set(module);
    this.errorMessage.set('');
    this.statusMessage.set('');

    if (module === 'admin') {
      this.loadAdminData();
    }
  }

  updateTenantForm(field: 'name' | 'code', value: string): void {
    this.tenantForm.update((form) => ({ ...form, [field]: value }));
    this.clearAdminMessages();
  }

  updateLocationForm(field: 'tenant_id' | 'name' | 'code' | 'astdb_family', value: string | number): void {
    this.locationForm.update((form) => ({ ...form, [field]: field === 'tenant_id' ? Number(value) : value }));
    this.clearAdminMessages();
  }

  updateImportForm(field: 'tenant_code' | 'tenant_name' | 'family', value: string): void {
    this.importForm.update((form) => ({ ...form, [field]: value }));
    this.importPreview.set(null);
    this.clearAdminMessages();
  }

  createTenant(): void {
    const payload = {
      name: this.tenantForm().name.trim(),
      code: this.tenantForm().code.trim()
    };

    if (!payload.name || !payload.code) {
      this.adminErrorMessage.set('Nombre y código del cliente son obligatorios.');
      return;
    }

    this.adminActionLoading.set(true);
    this.clearAdminMessages();
    this.api.createAdminTenant(payload).subscribe({
      next: (tenant) => {
        this.adminActionLoading.set(false);
        this.tenantForm.set({ name: '', code: '' });
        this.locationForm.update((form) => ({ ...form, tenant_id: tenant.id }));
        this.setAdminStatusMessage('Cliente creado correctamente.');
        this.loadAdminData();
      },
      error: (error: unknown) => {
        this.adminActionLoading.set(false);
        this.adminErrorMessage.set(this.resolveErrorMessage(error));
      }
    });
  }

  createLocation(): void {
    const payload = {
      tenant_id: this.locationForm().tenant_id,
      name: this.locationForm().name.trim(),
      code: this.locationForm().code.trim(),
      astdb_family: this.locationForm().astdb_family.trim()
    };

    if (!payload.tenant_id || !payload.name || !payload.code || !payload.astdb_family) {
      this.adminErrorMessage.set('Cliente, nombre, código y familia AstDB son obligatorios.');
      return;
    }

    this.adminActionLoading.set(true);
    this.clearAdminMessages();
    this.api.createAdminLocation(payload).subscribe({
      next: () => {
        this.adminActionLoading.set(false);
        this.locationForm.set({ tenant_id: payload.tenant_id, name: '', code: '', astdb_family: '' });
        this.setAdminStatusMessage('Call center creado correctamente.');
        this.loadAdminData();
        this.loadLocations();
      },
      error: (error: unknown) => {
        this.adminActionLoading.set(false);
        this.adminErrorMessage.set(this.resolveErrorMessage(error));
      }
    });
  }

  inspectAsterisk(): void {
    this.adminActionLoading.set(true);
    this.clearAdminMessages();
    this.api.inspectAsterisk().subscribe({
      next: (result) => {
        this.adminActionLoading.set(false);
        this.asteriskInspect.set(result);
        this.setAdminStatusMessage('Inspección de Asterisk actualizada.');
      },
      error: (error: unknown) => {
        this.adminActionLoading.set(false);
        this.adminErrorMessage.set(this.resolveErrorMessage(error));
      }
    });
  }

  previewAstdbImport(): void {
    const payload = this.normalizedImportPayload();

    if (!payload.tenant_code) {
      this.adminErrorMessage.set('El código del cliente es obligatorio para importar.');
      return;
    }

    this.adminActionLoading.set(true);
    this.clearAdminMessages();
    this.api.previewAsteriskImport(payload).subscribe({
      next: (preview) => {
        this.adminActionLoading.set(false);
        this.importPreview.set(preview);
        this.setAdminStatusMessage('Vista previa lista. Revisa antes de importar.');
      },
      error: (error: unknown) => {
        this.adminActionLoading.set(false);
        this.importPreview.set(null);
        this.adminErrorMessage.set(this.resolveErrorMessage(error));
      }
    });
  }

  importAstdbSchedules(): void {
    const payload = this.normalizedImportPayload();

    if (!payload.tenant_code) {
      this.adminErrorMessage.set('El código del cliente es obligatorio para importar.');
      return;
    }

    this.adminActionLoading.set(true);
    this.clearAdminMessages();
    this.api.importAsteriskSchedules(payload).subscribe({
      next: (result) => {
        this.adminActionLoading.set(false);
        this.importPreview.set(null);
        this.setAdminStatusMessage(`Importación completa: ${result.imported_days} día(s) importados.`);
        this.loadAdminData();
        this.loadLocations();
      },
      error: (error: unknown) => {
        this.adminActionLoading.set(false);
        this.adminErrorMessage.set(this.resolveErrorMessage(error));
      }
    });
  }

  processSyncJobs(retryFailed = false): void {
    this.adminActionLoading.set(true);
    this.clearAdminMessages();
    this.api
      .processSyncJobs({
        limit: 50,
        retry_failed: retryFailed,
        max_attempts: 5
      })
      .subscribe({
        next: (result) => {
          this.adminActionLoading.set(false);
          this.setAdminStatusMessage(
            `Procesados: ${result.processed}. Sincronizados: ${result.synced}. Fallidos: ${result.failed}.`
          );
          this.loadAdminData();
          this.refreshSelected();
        },
        error: (error: unknown) => {
          this.adminActionLoading.set(false);
          this.adminErrorMessage.set(this.resolveErrorMessage(error));
        }
      });
  }

  formatFamilyDays(family: AsteriskFamilyPreview): string {
    return family.days.map((day) => day.day_of_week).join(', ') || 'Sin días semanales';
  }

  addRule(days?: Weekday[], ranges?: TimeRange[]): void {
    this.clearSaveMessages();
    const selectedDays = days ?? this.firstAvailableDay();

    if (selectedDays.length === 0) {
      this.errorMessage.set('Todos los días ya tienen horario. Quita un día de otro bloque para crear uno nuevo.');
      return;
    }

    this.scheduleRules.update((rules) => [
      ...rules,
      {
        id: this.nextRuleId++,
        days: selectedDays,
        ranges: (ranges ?? this.defaultRanges()).map((range) => ({ ...range }))
      }
    ]);
  }

  removeRule(ruleId: number): void {
    this.clearSaveMessages();
    this.scheduleRules.update((rules) => rules.filter((rule) => rule.id !== ruleId));
  }

  toggleRuleDay(rule: ScheduleRule, day: Weekday, checked: boolean): void {
    this.clearSaveMessages();
    this.scheduleRules.update((rules) =>
      rules
        .map((item) => {
          if (item.id === rule.id) {
            return {
              ...item,
              days: checked
                ? this.sortDays([...new Set([...item.days, day])])
                : item.days.filter((selectedDay) => selectedDay !== day)
            };
          }

          return checked
            ? {
                ...item,
                days: item.days.filter((selectedDay) => selectedDay !== day)
              }
            : item;
        })
        .filter((item) => item.days.length > 0)
    );
  }

  addRange(rule: ScheduleRule): void {
    this.clearSaveMessages();
    rule.ranges.push({ start: '08:00', end: '12:00' });
    this.scheduleRules.update((rules) => [...rules]);
  }

  removeRange(rule: ScheduleRule, rangeIndex: number): void {
    if (rule.ranges.length <= 1) {
      return;
    }

    this.clearSaveMessages();
    rule.ranges.splice(rangeIndex, 1);
    this.scheduleRules.update((rules) => [...rules]);
  }

  applyWorkweekTemplate(): void {
    this.clearSaveMessages();
    this.scheduleRules.set([
      {
        id: this.nextRuleId++,
        days: [...workdays],
        ranges: this.defaultRanges()
      }
    ]);
  }

  copyRuleToWorkdays(rule: ScheduleRule): void {
    this.clearSaveMessages();
    this.scheduleRules.update((rules) =>
      rules
        .map((item) => {
          if (item.id === rule.id) {
            return {
              ...item,
              days: [...workdays]
            };
          }

          return {
            ...item,
            days: item.days.filter((day) => !workdays.includes(day))
          };
        })
        .filter((item) => item.id === rule.id || item.days.length > 0)
    );
  }

  updateRangeValue(ruleId: number, rangeIndex: number, field: keyof TimeRange, value: string): void {
    this.clearSaveMessages();
    this.scheduleRules.update((rules) =>
      rules.map((rule) => {
        if (rule.id !== ruleId) {
          return rule;
        }

        return {
          ...rule,
          ranges: rule.ranges.map((range, index) =>
            index === rangeIndex
              ? {
                  ...range,
                  [field]: value
                }
              : range
          )
        };
      })
    );
  }

  updateReason(value: string): void {
    this.reason.set(value);
    this.clearSaveMessages();
  }

  isDaySelected(rule: ScheduleRule, day: Weekday): boolean {
    return rule.days.includes(day);
  }

  formatRuleDays(rule: ScheduleRule): string {
    if (rule.days.length === 0) {
      return 'Sin días asignados';
    }

    return weekdays
      .filter(({ day }) => rule.days.includes(day))
      .map(({ shortLabel }) => shortLabel)
      .join(', ');
  }

  formatRanges(ranges: TimeRange[]): string {
    return ranges.map((range) => `${range.start}-${range.end}`).join(' | ');
  }

  runPreview(): void {
    const location = this.selectedLocation();

    if (!location || this.previewLoading()) {
      return;
    }

    if (!this.hasScheduleChanges()) {
      this.setStatusMessage('No hay cambios pendientes para previsualizar.');
      return;
    }

    const validationError = this.validateScheduleChanges();

    if (validationError) {
      this.errorMessage.set(validationError);
      this.previewActions.set([]);
      return;
    }

    this.previewLoading.set(true);
    this.statusMessage.set('');
    this.errorMessage.set('');

    this.api
      .previewSchedule(location.id, {
        timezone: 'America/Bogota',
        days: this.daysForUpdate()
      })
      .subscribe({
        next: (preview) => {
          this.previewLoading.set(false);
          this.previewActions.set(preview.actions);
        },
        error: (error: unknown) => {
          this.previewLoading.set(false);
          this.previewActions.set([]);
          this.errorMessage.set(this.resolveErrorMessage(error));
        }
      });
  }

  saveSchedule(): void {
    const location = this.selectedLocation();
    const trimmedReason = this.reason().trim();

    if (!location || this.saving()) {
      return;
    }

    if (!this.hasScheduleChanges()) {
      this.setStatusMessage('No hay cambios pendientes por guardar.');
      return;
    }

    const validationError = this.validateScheduleChanges();

    if (validationError) {
      this.errorMessage.set(validationError);
      return;
    }

    if (!trimmedReason) {
      this.errorMessage.set('El motivo del cambio es obligatorio.');
      return;
    }

    if (trimmedReason.length < 8) {
      this.errorMessage.set('El motivo debe tener al menos 8 caracteres.');
      return;
    }

    if (trimmedReason.length > 250) {
      this.errorMessage.set('El motivo no puede superar 250 caracteres.');
      return;
    }

    this.saving.set(true);
    this.errorMessage.set('');
    this.statusMessage.set('');

    this.api
      .updateSchedule(location.id, {
        timezone: 'America/Bogota',
        reason: trimmedReason,
        days: this.daysForUpdate()
      })
      .subscribe({
        next: (snapshot) => {
          this.saving.set(false);
          this.reason.set('');
          this.previewActions.set([]);
          this.applySnapshot(snapshot);
          this.loadChangeLogs(location.id);
          this.setStatusMessage(this.messageForSavedSchedule(snapshot));
        },
        error: (error: unknown) => {
          this.saving.set(false);
          this.errorMessage.set(this.resolveErrorMessage(error));
        }
      });
  }

  logout(): void {
    this.auth.logout().subscribe({
      next: () => void this.router.navigateByUrl('/login', { replaceUrl: true }),
      error: () => void this.router.navigateByUrl('/login', { replaceUrl: true })
    });
  }

  @HostListener('window:pageshow', ['$event'])
  revalidateRestoredSession(event: PageTransitionEvent): void {
    if (!event.persisted) {
      return;
    }

    this.auth.me().subscribe({
      error: () => {
        this.auth.clearSessionState();
        void this.router.navigateByUrl('/login', { replaceUrl: true });
      }
    });
  }

  private loadLocations(): void {
    this.api.getLocations().subscribe({
      next: (locations) => {
        this.locations.set(locations);
        this.loading.set(false);

        if (locations.length > 0) {
          this.selectLocation(locations[0]);
        }
      },
      error: () => {
        this.loading.set(false);
        this.errorMessage.set('No se pudieron cargar los call centers.');
      }
    });
  }

  private loadAdminData(): void {
    if (!this.isSuperuser()) {
      return;
    }

    this.adminLoading.set(true);
    this.api.getAdminTenants().subscribe({
      next: (tenants) => {
        this.adminTenants.set(tenants);
        if (tenants.length > 0 && this.locationForm().tenant_id === 0) {
          this.locationForm.update((form) => ({ ...form, tenant_id: tenants[0].id }));
        }
      },
      error: () => this.adminErrorMessage.set('No se pudieron cargar los clientes.')
    });
    this.api.getAdminLocations().subscribe({
      next: (locations) => this.adminLocations.set(locations),
      error: () => this.adminErrorMessage.set('No se pudieron cargar los call centers.')
    });
    this.api.getSyncJobs().subscribe({
      next: (jobs) => {
        this.syncJobs.set(jobs);
        this.adminLoading.set(false);
      },
      error: () => {
        this.syncJobs.set([]);
        this.adminLoading.set(false);
      }
    });
  }

  private loadSchedule(locationId: number): void {
    this.api.getSchedule(locationId).subscribe({
      next: (snapshot) => this.applySnapshot(snapshot),
      error: () => this.errorMessage.set('No se pudo cargar el horario.')
    });
  }

  private loadChangeLogs(locationId: number): void {
    this.api.getChangeLogs(locationId).subscribe({
      next: (logs) => this.changeLogs.set(logs),
      error: () => this.changeLogs.set([])
    });
  }

  private applySnapshot(snapshot: ScheduleSnapshot): void {
    const groupedRules = new Map<string, ScheduleRule>();
    const originalDays = emptyScheduleDays();

    this.syncStatus.set(snapshot.sync_status ?? null);
    this.lastSyncError.set(snapshot.last_sync_error ?? '');

    for (const { day } of weekdays) {
      const ranges = this.normalizedRanges(snapshot.days[day] ?? []);
      originalDays[day] = ranges;

      if (ranges.length === 0) {
        continue;
      }

      const key = this.rangesKey(ranges);
      const existingRule = groupedRules.get(key);

      if (existingRule) {
        existingRule.days.push(day);
        continue;
      }

      groupedRules.set(key, {
        id: this.nextRuleId++,
        days: [day],
        ranges
      });
    }

    this.originalScheduleDays.set(originalDays);
    this.scheduleRules.set(
      Array.from(groupedRules.values()).map((rule) => ({
        ...rule,
        days: this.sortDays(rule.days)
      }))
    );
  }

  private firstAvailableDay(): Weekday[] {
    const assignedDays = this.assignedDays();
    const availableDay = weekdays.find(({ day }) => !assignedDays.has(day));

    return availableDay ? [availableDay.day] : [];
  }

  private defaultRanges(): TimeRange[] {
    return [
      { start: '08:00', end: '12:00' },
      { start: '14:00', end: '18:00' }
    ];
  }

  private daysForUpdate(): Array<{ day_of_week: Weekday; ranges: TimeRange[] }> {
    return weekdays
      .filter(({ day }) => this.assignedDays().has(day))
      .map(({ day }) => ({
        day_of_week: day,
        ranges: this.normalizedRanges(this.rangesForAssignedDay(day))
      }));
  }

  private rangesForAssignedDay(day: Weekday): TimeRange[] {
    const rule = this.scheduleRules().find((item) => item.days.includes(day));

    return rule ? rule.ranges.map((range) => ({ ...range })) : [];
  }

  private sortDays(days: Weekday[]): Weekday[] {
    return [...days].sort(
      (first, second) =>
        weekdays.findIndex(({ day }) => day === first) -
        weekdays.findIndex(({ day }) => day === second)
    );
  }

  private rangesKey(ranges: TimeRange[]): string {
    return this.normalizedRanges(ranges).map((range) => `${range.start}-${range.end}`).join('|');
  }

  private normalizedRanges(ranges: TimeRange[]): TimeRange[] {
    return ranges
      .map((range) => ({
        start: range.start.trim(),
        end: range.end.trim()
      }))
      .sort((first, second) => this.timeToMinutes(first.start) - this.timeToMinutes(second.start));
  }

  private validateScheduleChanges(): string {
    for (const { day_of_week, ranges } of this.daysForUpdate()) {
      const dayLabel = this.labelForDay(day_of_week);

      if (ranges.length === 0) {
        return `${dayLabel} no tiene franjas configuradas.`;
      }

      for (const range of ranges) {
        if (!timePattern.test(range.start) || !timePattern.test(range.end)) {
          return `${dayLabel} tiene una hora inválida. Usa el formato 08:00 o 14:30.`;
        }

        if (this.timeToMinutes(range.start) >= this.timeToMinutes(range.end)) {
          return `${dayLabel} tiene una franja donde la hora de inicio no es menor que la de fin.`;
        }
      }

      for (let index = 1; index < ranges.length; index += 1) {
        const previous = ranges[index - 1];
        const current = ranges[index];

        if (this.timeToMinutes(current.start) < this.timeToMinutes(previous.end)) {
          return `${dayLabel} tiene franjas solapadas. Ajusta los rangos antes de guardar.`;
        }
      }
    }

    return '';
  }

  private timeToMinutes(value: string): number {
    if (!timePattern.test(value)) {
      return Number.POSITIVE_INFINITY;
    }

    const [hours, minutes] = value.split(':').map(Number);

    return hours * 60 + minutes;
  }

  private labelForDay(day: Weekday): string {
    return weekdays.find((weekday) => weekday.day === day)?.label ?? day;
  }

  private clearSaveMessages(): void {
    this.clearStatusMessageTimer();
    this.statusMessage.set('');
    this.errorMessage.set('');
    this.previewActions.set([]);
  }

  private clearAdminMessages(): void {
    this.clearAdminStatusMessageTimer();
    this.adminStatusMessage.set('');
    this.adminErrorMessage.set('');
  }

  private setStatusMessage(message: string): void {
    this.clearStatusMessageTimer();
    this.statusMessage.set(message);
    this.statusMessageTimer = setTimeout(() => {
      if (this.statusMessage() === message) {
        this.statusMessage.set('');
      }
    }, 5000);
  }

  private setAdminStatusMessage(message: string): void {
    this.clearAdminStatusMessageTimer();
    this.adminStatusMessage.set(message);
    this.adminStatusMessageTimer = setTimeout(() => {
      if (this.adminStatusMessage() === message) {
        this.adminStatusMessage.set('');
      }
    }, 5000);
  }

  private clearStatusMessageTimer(): void {
    if (!this.statusMessageTimer) {
      return;
    }

    clearTimeout(this.statusMessageTimer);
    this.statusMessageTimer = null;
  }

  private clearAdminStatusMessageTimer(): void {
    if (!this.adminStatusMessageTimer) {
      return;
    }

    clearTimeout(this.adminStatusMessageTimer);
    this.adminStatusMessageTimer = null;
  }

  private normalizedImportPayload(): { tenant_code: string; tenant_name?: string; family?: string } {
    const form = this.importForm();
    const payload: { tenant_code: string; tenant_name?: string; family?: string } = {
      tenant_code: form.tenant_code.trim()
    };

    if (form.tenant_name.trim()) {
      payload.tenant_name = form.tenant_name.trim();
    }

    if (form.family.trim()) {
      payload.family = form.family.trim();
    }

    return payload;
  }

  private messageForSavedSchedule(snapshot: ScheduleSnapshot): string {
    if (snapshot.sync_status === 'synced') {
      return 'Horario guardado y sincronizado con Asterisk.';
    }

    if (snapshot.sync_status === 'failed') {
      return 'Horario guardado, pero falló la sincronización con Asterisk. Revisa el error AMI.';
    }

    return 'Horario guardado. Sincronización pendiente con Asterisk.';
  }

  private resolveErrorMessage(error: unknown): string {
    if (
      typeof error === 'object' &&
      error !== null &&
      'error' in error &&
      typeof (error as { error?: unknown }).error === 'object'
    ) {
      const payload = (error as { error?: { detail?: string } }).error;

      if (payload?.detail) {
        return payload.detail;
      }
    }

    return 'No se pudo guardar el horario.';
  }
}
