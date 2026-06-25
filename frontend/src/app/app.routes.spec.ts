import { routes } from './app.routes';
import { DashboardComponent } from './features/dashboard/dashboard.component';
import { LoginComponent } from './features/login/login.component';

describe('routes', () => {
  it('declara las rutas principales de sesion y dashboard', () => {
    expect(routes).toContain(
      jasmine.objectContaining({
        path: 'login',
        component: LoginComponent
      })
    );
    expect(routes).toContain(
      jasmine.objectContaining({
        path: '',
        component: DashboardComponent
      })
    );
    expect(routes).toContain(
      jasmine.objectContaining({
        path: '**',
        redirectTo: ''
      })
    );
  });
});
