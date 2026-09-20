import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from './stores/auth'
import AuthLayout from './layouts/AuthLayout.vue'
import AppLayout from './layouts/AppLayout.vue'
import LoginView from './views/LoginView.vue'
import RegisterView from './views/RegisterView.vue'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: AuthLayout,
    children: [
      { path: 'login', name: 'login', component: LoginView, meta: { public: true } },
      { path: 'register', name: 'register', component: RegisterView, meta: { public: true } },
    ],
  },
  {
    path: '/',
    component: AppLayout,
    children: [
      { path: 'home', name: 'home', component: () => import('./views/HomeView.vue') },
      {
        path: 'account/password',
        name: 'password',
        component: () => import('./views/PasswordView.vue'),
      },
      {
        path: 'account/contacts',
        name: 'contacts',
        component: () => import('./views/ContactsView.vue'),
      },
      {
        path: 'student/application',
        name: 'application',
        component: () => import('./views/ApplicationView.vue'),
        meta: { roles: ['STUDENT'] },
      },
      {
        path: 'staff/reviews',
        name: 'reviews',
        component: () => import('./views/ReviewsView.vue'),
        meta: { roles: ['TEACHER', 'ADMIN'], active: true },
      },
      {
        path: 'admin/accounts',
        name: 'accounts',
        component: () => import('./views/AccountsView.vue'),
        meta: { roles: ['ADMIN'], active: true },
      },
      {
        path: 'classes',
        name: 'classes',
        component: () => import('./views/ClassesView.vue'),
        meta: { roles: ['TEACHER', 'ADMIN'], active: true },
      },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/home' },
]

const router = createRouter({ history: createWebHistory(), routes })

function landingRoute(auth: ReturnType<typeof useAuthStore>): string {
  const user = auth.user
  if (!user) return '/login'
  if (user.must_change_password) return '/account/password'
  if (user.user_type === 'STUDENT' && user.status === 'WAITING_ACTIVATE')
    return '/student/application'
  return '/home'
}

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.ready) await auth.restore()
  if (to.meta.public) return auth.user ? landingRoute(auth) : true
  if (!auth.user) return { name: 'login', query: { redirect: to.fullPath } }
  if (auth.user.must_change_password && to.name !== 'password') return { name: 'password' }
  if (auth.user.user_type === 'STUDENT' && auth.user.status === 'WAITING_ACTIVATE') {
    const allowed = new Set(['application', 'contacts', 'password'])
    if (!allowed.has(String(to.name))) return { name: 'application' }
  }
  const roles = to.meta.roles as string[] | undefined
  if (roles && !roles.includes(auth.user.user_type)) return landingRoute(auth)
  if (to.meta.active && auth.user.status !== 'ACTIVATED') return landingRoute(auth)
  return true
})

window.addEventListener('auth:expired', () => {
  useAuthStore().clear()
  void router.push({ name: 'login', query: { expired: '1' } })
})
export default router
