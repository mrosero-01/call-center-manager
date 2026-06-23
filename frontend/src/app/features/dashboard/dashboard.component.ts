import { CommonModule } from '@angular/common';
import { Component, HostListener, OnInit, computed, signal } from '@angular/core';
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
  CallCenterLocation,
  CurrentUser,
  ScheduleChangeLog,
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
export class DashboardComponent implements OnInit {
  readonly weekdays = weekdays;
  readonly user = signal<CurrentUser | null>(null);
  readonly locations = signal<CallCenterLocation[]>([]);
  readonly selectedLocation = signal<CallCenterLocation | null>(null);
  readonly scheduleRules = signal<ScheduleRule[]>([]);
  readonly changeLogs = signal<ScheduleChangeLog[]>([]);
  readonly reason = signal('');
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly statusMessage = signal('');
  readonly errorMessage = signal('');

  private nextRuleId = 1;

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

  selectLocation(location: CallCenterLocation): void {
    this.selectedLocation.set(location);
    this.reason.set('');
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
    const location = this.selectedLocation();

    if (!location) {
      return;
    }

    this.loadSchedule(location.id);
    this.loadChangeLogs(location.id);
  }

  addRule(days?: Weekday[], ranges?: TimeRange[]): void {
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
    this.scheduleRules.update((rules) => rules.filter((rule) => rule.id !== ruleId));
  }

  toggleRuleDay(rule: ScheduleRule, day: Weekday, checked: boolean): void {
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
    rule.ranges.push({ start: '08:00', end: '12:00' });
    this.scheduleRules.update((rules) => [...rules]);
  }

  removeRange(rule: ScheduleRule, rangeIndex: number): void {
    if (rule.ranges.length <= 1) {
      return;
    }

    rule.ranges.splice(rangeIndex, 1);
    this.scheduleRules.update((rules) => [...rules]);
  }

  applyWorkweekTemplate(): void {
    this.scheduleRules.set([
      {
        id: this.nextRuleId++,
        days: [...workdays],
        ranges: this.defaultRanges()
      }
    ]);
  }

  copyRuleToWorkdays(rule: ScheduleRule): void {
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

  saveSchedule(): void {
    const location = this.selectedLocation();
    const trimmedReason = this.reason().trim();

    if (!location || this.saving()) {
      return;
    }

    if (!trimmedReason) {
      this.errorMessage.set('El motivo del cambio es obligatorio.');
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
          this.applySnapshot(snapshot);
          this.loadChangeLogs(location.id);
          this.statusMessage.set('Horario guardado y sincronizado.');
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

    for (const { day } of weekdays) {
      const ranges = snapshot.days[day] ?? [];

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
        ranges: ranges.map((range) => ({ ...range }))
      });
    }

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
        ranges: this.rangesForAssignedDay(day)
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
    return ranges.map((range) => `${range.start}-${range.end}`).join('|');
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
