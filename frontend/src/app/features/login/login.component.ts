import { Component, OnInit, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { LucideEye, LucideEyeOff, LucideLogIn, LucideShieldCheck } from '@lucide/angular';

import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [ReactiveFormsModule, LucideEye, LucideEyeOff, LucideLogIn, LucideShieldCheck],
  templateUrl: './login.component.html',
  styleUrl: './login.component.css'
})
export class LoginComponent implements OnInit {
  readonly loading = signal(false);
  readonly errorMessage = signal('');
  readonly submitted = signal(false);
  readonly showPassword = signal(false);

  readonly form = this.formBuilder.nonNullable.group({
    username: ['', [Validators.required]],
    password: ['', [Validators.required]]
  });

  constructor(
    private readonly auth: AuthService,
    private readonly formBuilder: FormBuilder,
    private readonly router: Router
  ) {}

  ngOnInit(): void {
    this.auth.ensureCsrfCookie().subscribe();
  }

  submit(): void {
    this.submitted.set(true);
    this.errorMessage.set('');

    if (this.form.invalid || this.loading()) {
      this.form.markAllAsTouched();
      this.errorMessage.set('Completa los campos obligatorios para continuar.');
      return;
    }

    this.loading.set(true);

    const { username, password } = this.form.getRawValue();

    this.auth.login(username.trim(), password).subscribe({
      next: () => {
        this.loading.set(false);
        void this.router.navigateByUrl('/');
      },
      error: () => {
        this.loading.set(false);
        this.errorMessage.set('Usuario o contraseña inválidos.');
      }
    });
  }

  togglePasswordVisibility(): void {
    this.showPassword.update((value) => !value);
  }

  shouldShowFieldError(fieldName: 'username' | 'password'): boolean {
    const field = this.form.controls[fieldName];

    return field.invalid && (field.touched || this.submitted());
  }

  fieldError(fieldName: 'username' | 'password'): string {
    const field = this.form.controls[fieldName];

    if (field.hasError('required')) {
      return fieldName === 'username'
        ? 'Ingresa tu usuario.'
        : 'Ingresa tu contraseña.';
    }

    return '';
  }
}
