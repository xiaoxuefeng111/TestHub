<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">{{ $t('uiAutomation.ai.title') }}</h1>
    </div>

    <div class="card-container">
      <el-row :gutter="20">
        <el-col :span="12">
          <div class="section-title">{{ $t('uiAutomation.ai.taskInput') }}</div>
          <el-form :model="taskForm" label-position="top">
            <el-form-item :label="$t('uiAutomation.ai.taskDescription')" required>
              <el-input
                v-model="taskForm.description"
                type="textarea"
                :rows="10"
                :placeholder="$t('uiAutomation.ai.taskPlaceholder')"
                maxlength="2000"
                show-word-limit
              />
            </el-form-item>

            <el-form-item :label="$t('uiAutomation.ai.gifRecording')">
              <el-switch
                v-model="taskForm.enableGif"
                :active-text="$t('uiAutomation.ai.on')"
                :inactive-text="$t('uiAutomation.ai.off')"
              />
              <span style="margin-left: 10px; color: #909399; font-size: 12px;">
                {{ $t('uiAutomation.ai.gifTip') }}
              </span>
            </el-form-item>

            <el-form-item>
              <el-button
                type="primary"
                @click="handleRun"
                :loading="running"
                :disabled="!taskForm.description"
              >
                <el-icon><VideoPlay /></el-icon>
                {{ $t('uiAutomation.ai.startExecution') }}
              </el-button>
              <el-button
                v-if="running"
                type="danger"
                @click="handleStop"
                :disabled="!running || analyzing"
              >
                <el-icon><SwitchButton /></el-icon>
                {{ $t('uiAutomation.ai.stopExecution') }}
              </el-button>
              <el-button
                type="success"
                @click="handleSaveAsTemplate"
                :disabled="!taskForm.description"
              >
                <el-icon><DocumentAdd /></el-icon>
                {{ templateButtonText }}
              </el-button>
              <el-button
                type="warning"
                @click="handleSaveAsAppTestCase"
                :disabled="!canSaveAsAppTestCase"
              >
                <el-icon><DocumentAdd /></el-icon>
                {{ appCaseButtonText }}
              </el-button>
            </el-form-item>
          </el-form>

          <el-alert
            :title="$t('uiAutomation.ai.tip')"
            type="info"
            :closable="false"
            style="margin-top: 20px;"
          >
            <template #default>
              <div>{{ $t('uiAutomation.ai.tipContent1') }}</div>
              <div>{{ $t('uiAutomation.ai.tipContent2') }}</div>
            </template>
          </el-alert>

          <div class="section-title" style="margin-top: 20px;">{{ $t('uiAutomation.ai.executionLogs') }}</div>
          <div class="log-container" ref="logContainer">
            <div v-if="!logs && !running" class="empty-logs">
              {{ $t('uiAutomation.ai.noLogs') }}
            </div>
            <pre v-else class="log-content">{{ logs }}</pre>
          </div>
        </el-col>

        <el-col :span="12">
          <div class="section-title">{{ $t('uiAutomation.ai.taskDetails') }}</div>
          <div class="task-list-container">
            <div v-if="analyzing" class="analyzing-state">
              <el-icon class="is-loading"><Loading /></el-icon>
              <span>{{ $t('uiAutomation.ai.analyzing') }}</span>
            </div>
            <div v-else-if="plannedTasks.length > 0">
              <div
                v-for="task in plannedTasks"
                :key="task.id"
                class="task-item"
                :class="task.status"
              >
                <div class="task-status-icon">
                  <el-icon v-if="task.status === 'completed'" color="#67C23A"><CircleCheckFilled /></el-icon>
                  <el-icon v-else-if="task.status === 'in_progress'" class="is-loading" color="#409EFF"><Loading /></el-icon>
                  <el-icon v-else color="#909399"><CircleCheck /></el-icon>
                </div>
                <div class="task-content">
                  <span class="task-id">{{ task.id }}.</span>
                  <span class="task-desc">{{ task.description }}</span>
                </div>
              </div>
            </div>
            <div v-else class="empty-tasks">
              {{ $t('uiAutomation.ai.noTasks') }}
            </div>
          </div>
        </el-col>
      </el-row>
    </div>

    <el-dialog v-model="showTemplateDialog" :title="templateDialogTitle" width="500px" :close-on-click-modal="false">
      <el-form :model="templateForm" :rules="templateRules" ref="templateFormRef" label-width="80px">
        <el-form-item :label="$t('uiAutomation.ai.caseName')" prop="name">
          <el-input v-model="templateForm.name" :placeholder="$t('uiAutomation.ai.caseNamePlaceholder')" />
        </el-form-item>
        <el-form-item :label="$t('uiAutomation.common.description')" prop="description">
          <el-input v-model="templateForm.description" type="textarea" :placeholder="$t('uiAutomation.ai.caseDescPlaceholder')" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showTemplateDialog = false">{{ $t('uiAutomation.common.cancel') }}</el-button>
          <el-button type="primary" @click="confirmSaveTemplate" :loading="savingTemplate">{{ $t('uiAutomation.common.save') }}</el-button>
        </span>
      </template>
    </el-dialog>

    <el-dialog v-model="showAppCaseDialog" title="保存为 APP 测试用例" width="500px" :close-on-click-modal="false">
      <el-form :model="appCaseForm" :rules="appCaseRules" ref="appCaseFormRef" label-width="80px">
        <el-form-item label="用例名称" prop="name">
          <el-input v-model="appCaseForm.name" placeholder="请输入 APP 测试用例名称" />
        </el-form-item>
        <el-form-item :label="$t('uiAutomation.common.description')" prop="description">
          <el-input v-model="appCaseForm.description" type="textarea" placeholder="可选：补充这条 APP 测试用例说明" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showAppCaseDialog = false">{{ $t('uiAutomation.common.cancel') }}</el-button>
          <el-button type="primary" @click="confirmSaveAppCase" :loading="savingAppCase">{{ $t('uiAutomation.common.save') }}</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { VideoPlay, DocumentAdd, CircleCheckFilled, CircleCheck, Loading, SwitchButton } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import {
  createAICase,
  getAIExecutionRecordDetail,
  runAdhocAITask,
  saveAIExecutionAsAppTestCase,
  stopAITask,
} from '@/api/ui_automation'

const { t } = useI18n()
const router = useRouter()

const running = ref(false)
const analyzing = ref(false)
const savingTemplate = ref(false)
const savingAppCase = ref(false)
const logs = ref('')
const plannedTasks = ref([])
const currentExecutionId = ref(null)
const currentExecutionRecord = ref(null)
const logContainer = ref(null)

const taskForm = reactive({
  description: '',
  enableGif: true,
})

const showTemplateDialog = ref(false)
const templateForm = reactive({
  name: '',
  description: '',
})
const templateFormRef = ref(null)

const showAppCaseDialog = ref(false)
const appCaseForm = reactive({
  name: '',
  description: '',
})
const appCaseFormRef = ref(null)

const templateRules = computed(() => ({
  name: [{ required: true, message: t('uiAutomation.ai.rules.nameRequired'), trigger: 'blur' }],
}))

const appCaseRules = {
  name: [{ required: true, message: '请输入 APP 测试用例名称', trigger: 'blur' }],
}

const canSaveAsAppTestCase = computed(() => Boolean(currentExecutionRecord.value?.can_save_as_app_test_case))
const savedAppTestCaseId = computed(() => currentExecutionRecord.value?.saved_app_test_case || null)
const templateButtonText = computed(() => '保存为 AI 模板')
const appCaseButtonText = computed(() => savedAppTestCaseId.value ? '查看 APP 测试用例' : '保存为 APP 测试用例')
const templateDialogTitle = computed(() => '保存为 AI 模板')

const handleRun = async () => {
  running.value = true
  analyzing.value = true
  logs.value = t('uiAutomation.ai.messages.initAgent')
  plannedTasks.value = []
  currentExecutionRecord.value = null
  currentExecutionId.value = null

  try {
    const response = await runAdhocAITask({
      task_description: taskForm.description,
      execution_mode: 'text',
      enable_gif: taskForm.enableGif,
    })

    currentExecutionId.value = response.data.execution_id
    ElMessage.success(t('uiAutomation.ai.messages.startSuccess'))
    pollLogs()
  } catch (error) {
    console.error('执行失败:', error)
    ElMessage.error(t('uiAutomation.ai.messages.startFailed') + ': ' + (error.response?.data?.error || error.message))
    running.value = false
    analyzing.value = false
  }
}

const handleStop = async () => {
  if (!currentExecutionId.value) return

  try {
    await stopAITask(currentExecutionId.value)
    ElMessage.warning(t('uiAutomation.ai.messages.stopping'))
  } catch (error) {
    console.error('停止失败:', error)
    ElMessage.error(t('uiAutomation.ai.messages.stopFailed'))
  }
}

const pollLogs = () => {
  const pollInterval = setInterval(async () => {
    if (!currentExecutionId.value) {
      clearInterval(pollInterval)
      return
    }

    try {
      const response = await getAIExecutionRecordDetail(currentExecutionId.value)
      const record = response.data
      currentExecutionRecord.value = record
      logs.value = record.logs || ''
      plannedTasks.value = record.planned_tasks || []

      if (plannedTasks.value.length > 0) {
        analyzing.value = false
      }

      nextTick(() => {
        if (logContainer.value) {
          logContainer.value.scrollTop = logContainer.value.scrollHeight
        }
      })

      if (['passed', 'failed', 'stopped'].includes(record.status)) {
        clearInterval(pollInterval)
        running.value = false
        analyzing.value = false
        if (record.status === 'passed') {
          ElMessage.success(t('uiAutomation.ai.messages.executionSuccess'))
        } else if (record.status === 'stopped') {
          ElMessage.warning(t('uiAutomation.ai.messages.taskStopped'))
        } else {
          ElMessage.error(t('uiAutomation.ai.messages.executionFailed'))
        }
      }
    } catch (error) {
      console.error('获取日志失败:', error)
    }
  }, 2000)
}

const handleSaveAsTemplate = () => {
  showTemplateDialog.value = true
  templateForm.name = ''
  templateForm.description = ''
}

const confirmSaveTemplate = async () => {
  if (!templateFormRef.value) return

  await templateFormRef.value.validate(async (valid) => {
    if (!valid) return

    savingTemplate.value = true
    try {
      await createAICase({
        name: templateForm.name,
        description: templateForm.description,
        task_description: taskForm.description,
      })
      ElMessage.success(t('uiAutomation.ai.messages.saveSuccess'))
      showTemplateDialog.value = false
    } catch (error) {
      console.error('保存 AI 模板失败:', error)
      ElMessage.error(t('uiAutomation.ai.messages.saveFailed'))
    } finally {
      savingTemplate.value = false
    }
  })
}

const handleSaveAsAppTestCase = () => {
  if (savedAppTestCaseId.value) {
    router.push('/app-automation/test-cases')
    return
  }
  if (!canSaveAsAppTestCase.value) {
    ElMessage.warning('当前执行记录暂不支持保存为 APP 测试用例')
    return
  }
  showAppCaseDialog.value = true
  appCaseForm.name = currentExecutionRecord.value?.case_name || taskForm.description.slice(0, 20) || ''
  appCaseForm.description = ''
}

const confirmSaveAppCase = async () => {
  if (!appCaseFormRef.value || !currentExecutionId.value) return

  await appCaseFormRef.value.validate(async (valid) => {
    if (!valid) return

    savingAppCase.value = true
    try {
      const response = await saveAIExecutionAsAppTestCase(currentExecutionId.value, {
        name: appCaseForm.name,
        description: appCaseForm.description,
      })
      ElMessage.success(response.data.already_saved ? '该执行记录已保存过 APP 测试用例' : '已保存为 APP 测试用例')
      showAppCaseDialog.value = false
      const latest = await getAIExecutionRecordDetail(currentExecutionId.value)
      currentExecutionRecord.value = latest.data
      router.push('/app-automation/test-cases')
    } catch (error) {
      console.error('保存 APP 测试用例失败:', error)
      ElMessage.error(error.response?.data?.error?.name || error.response?.data?.error || '保存 APP 测试用例失败')
    } finally {
      savingAppCase.value = false
    }
  })
}
</script>

<style lang="scss" scoped>
.page-container {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;

  .page-title {
    font-size: 20px;
    font-weight: 600;
    margin: 0;
  }
}

.card-container {
  background-color: #fff;
  border-radius: 4px;
  padding: 20px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  min-height: calc(100vh - 140px);
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 15px;
  padding-left: 10px;
  border-left: 4px solid #409eff;
}

.task-list-container {
  background-color: #f5f7fa;
  border-radius: 4px;
  padding: 15px;
  margin-bottom: 20px;
  height: calc(100vh - 200px);
  overflow-y: auto;

  .task-item {
    display: flex;
    align-items: flex-start;
    padding: 10px;
    border-bottom: 1px solid #e4e7ed;
    transition: all 0.3s;

    &:last-child {
      border-bottom: none;
    }

    &.completed {
      background-color: #f0f9eb;
      .task-desc {
        color: #67c23a;
        text-decoration: line-through;
      }
    }

    &.in_progress {
      background-color: #ecf5ff;
      .task-desc {
        color: #409eff;
        font-weight: bold;
      }
    }

    .task-status-icon {
      margin-right: 10px;
      margin-top: 2px;
      font-size: 16px;
    }

    .task-content {
      flex: 1;
      line-height: 1.5;

      .task-id {
        font-weight: bold;
        margin-right: 5px;
      }
    }
  }
}

.empty-tasks {
  color: #909399;
  text-align: center;
  padding: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.analyzing-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #409eff;

  .el-icon {
    font-size: 24px;
    margin-bottom: 10px;
  }
}

.log-container {
  background-color: #1e1e1e;
  border-radius: 4px;
  height: 300px;
  overflow-y: auto;
  padding: 15px;
  color: #fff;
  font-family: 'Consolas', 'Monaco', monospace;

  .empty-logs {
    color: #909399;
    text-align: center;
    margin-top: 100px;
  }

  .log-content {
    margin: 0;
    white-space: pre-wrap;
    word-wrap: break-word;
    font-size: 14px;
    line-height: 1.5;
  }
}
</style>
